/**
 * Production-ready logging utility for frontend
 * Provides structured logging with different levels and remote error reporting
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: string;
  data?: any;
  error?: {
    message: string;
    stack?: string;
    name?: string;
  };
  browser?: {
    userAgent: string;
    url: string;
    referrer: string;
  };
  user?: {
    id?: string;
    email?: string;
    role?: string;
  };
}

class Logger {
  private isDevelopment = import.meta.env.DEV;
  private isProduction = import.meta.env.PROD;
  private enableRemoteLogging = true;
  private logBuffer: LogEntry[] = [];
  private maxBufferSize = 50;
  private apiEndpoint = import.meta.env.VITE_API_BASE_URL || '';

  constructor() {
    // Set up global error handler
    this.setupGlobalErrorHandler();
    // Set up unhandled promise rejection handler
    this.setupUnhandledRejectionHandler();
    // Periodically flush logs to server
    if (this.isProduction && this.enableRemoteLogging) {
      setInterval(() => this.flushLogs(), 30000); // Every 30 seconds
    }
  }

  private setupGlobalErrorHandler() {
    window.addEventListener('error', (event) => {
      this.error('Uncaught error', 'global', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error
      });
    });
  }

  private setupUnhandledRejectionHandler() {
    window.addEventListener('unhandledrejection', (event) => {
      this.error('Unhandled promise rejection', 'promise', {
        reason: event.reason,
        promise: event.promise
      });
    });
  }

  private createLogEntry(
    level: LogLevel,
    message: string,
    context?: string,
    data?: any
  ): LogEntry {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      context,
      data,
      browser: {
        userAgent: navigator.userAgent,
        url: window.location.href,
        referrer: document.referrer
      }
    };

    // Add user info if available
    try {
      const userProfile = localStorage.getItem('secureStorage_userProfile');
      if (userProfile) {
        const profile = JSON.parse(userProfile);
        entry.user = {
          id: profile.value?.id,
          email: profile.value?.email,
          role: profile.value?.role
        };
      }
    } catch (e) {
      // Ignore errors reading user profile
    }

    // Add error details if present
    if (data instanceof Error) {
      entry.error = {
        message: data.message,
        stack: data.stack,
        name: data.name
      };
    }

    return entry;
  }

  private log(level: LogLevel, message: string, context?: string, data?: any) {
    const entry = this.createLogEntry(level, message, context, data);

    // Always log to console in development
    if (this.isDevelopment || level === 'error' || level === 'warn') {
      const consoleMethod = level === 'error' ? 'error' : level === 'warn' ? 'warn' : 'log';
      const prefix = `[${entry.timestamp}] [${level.toUpperCase()}]${context ? ` [${context}]` : ''}`;
      console[consoleMethod](prefix, message, data || '');
    }

    // In production, buffer logs for batch sending
    if (this.isProduction && this.enableRemoteLogging) {
      this.logBuffer.push(entry);
      
      // Flush if buffer is full
      if (this.logBuffer.length >= this.maxBufferSize) {
        this.flushLogs();
      }

      // Immediately send errors
      if (level === 'error') {
        this.flushLogs();
      }
    }
  }

  private async flushLogs() {
    if (this.logBuffer.length === 0) return;

    const logsToSend = [...this.logBuffer];
    this.logBuffer = [];

    try {
      // Only send to backend if we have a valid endpoint
      if (this.apiEndpoint) {
        await fetch(`${this.apiEndpoint}/api/v1/logs/frontend`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ logs: logsToSend })
        });
      }
    } catch (error) {
      // Don't log errors about logging to avoid infinite loop
      console.error('Failed to send logs to server:', error);
    }
  }

  debug(message: string, context?: string, data?: any) {
    if (this.isDevelopment) {
      this.log('debug', message, context, data);
    }
  }

  info(message: string, context?: string, data?: any) {
    this.log('info', message, context, data);
  }

  warn(message: string, context?: string, data?: any) {
    this.log('warn', message, context, data);
  }

  error(message: string, context?: string, data?: any) {
    this.log('error', message, context, data);
  }

  // Network request logging
  logApiRequest(method: string, url: string, data?: any) {
    this.debug(`API Request: ${method} ${url}`, 'api', data);
  }

  logApiResponse(method: string, url: string, status: number, data?: any) {
    const level = status >= 400 ? 'error' : 'debug';
    this.log(level, `API Response: ${method} ${url} - ${status}`, 'api', data);
  }

  logApiError(method: string, url: string, error: any) {
    this.error(`API Error: ${method} ${url}`, 'api', error);
  }

  // Auth-specific logging
  logAuthEvent(event: string, data?: any) {
    this.info(`Auth: ${event}`, 'auth', data);
  }

  logAuthError(event: string, error: any) {
    this.error(`Auth Error: ${event}`, 'auth', error);
  }

  // Performance logging
  logPerformance(metric: string, value: number, data?: any) {
    this.info(`Performance: ${metric} = ${value}ms`, 'performance', data);
  }

  // User action logging
  logUserAction(action: string, data?: any) {
    this.info(`User Action: ${action}`, 'user', data);
  }

  // Navigation logging
  logNavigation(from: string, to: string, data?: any) {
    this.info(`Navigation: ${from} → ${to}`, 'navigation', data);
  }

  // Feature flag logging
  logFeatureFlag(flag: string, enabled: boolean) {
    this.debug(`Feature Flag: ${flag} = ${enabled}`, 'feature');
  }

  // Flush logs before page unload
  flush() {
    if (this.isProduction && this.enableRemoteLogging) {
      this.flushLogs();
    }
  }
}

// Create singleton instance
const logger = new Logger();

// Flush logs before page unload
window.addEventListener('beforeunload', () => {
  logger.flush();
});

export default logger;