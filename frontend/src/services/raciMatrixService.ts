import { apiClient } from './api/client';
import {
  RaciMatrix,
  CreateRaciMatrixPayload,
  UpdateRaciMatrixPayload,
  CreateRaciMatrixResponse,
  RaciMatrixType,
  RaciMatrixTemplate,
  RaciValidationResult
} from '@/types/entities';

export const raciMatrixService = {
  // Get all RACI matrices
  async getAllMatrices(): Promise<RaciMatrix[]> {
    const response = await apiClient.get('/api/v1/raci-matrices/');
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Get a specific RACI matrix by ID
  async getMatrixById(matrixId: string): Promise<RaciMatrix> {
    const response = await apiClient.get(`/api/v1/raci-matrices/${matrixId}`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Get RACI matrices by type
  async getMatricesByType(matrixType: RaciMatrixType): Promise<RaciMatrix[]> {
    const response = await apiClient.get(`/api/v1/raci-matrices/type/${matrixType}`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Create a new RACI matrix
  async createMatrix(payload: CreateRaciMatrixPayload): Promise<CreateRaciMatrixResponse> {
    const response = await apiClient.post('/api/v1/raci-matrices/', payload);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Update an existing RACI matrix
  async updateMatrix(matrixId: string, payload: UpdateRaciMatrixPayload): Promise<CreateRaciMatrixResponse> {
    const response = await apiClient.put(`/api/v1/raci-matrices/${matrixId}`, payload);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Delete a RACI matrix
  async deleteMatrix(matrixId: string): Promise<{ message: string }> {
    const response = await apiClient.delete(`/api/v1/raci-matrices/${matrixId}`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Validate a RACI matrix
  async validateMatrix(matrixId: string): Promise<{ is_valid: boolean; errors: string[] }> {
    const response = await apiClient.post(`/api/v1/raci-matrices/${matrixId}/validate`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Run comprehensive validation
  async validateMatrixComplete(matrixId: string): Promise<RaciValidationResult> {
    const response = await apiClient.post(`/api/v1/raci-matrices/${matrixId}/validate-complete`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Get matrix templates
  async getTemplates(): Promise<RaciMatrixTemplate[]> {
    const response = await apiClient.get('/api/v1/raci-matrices/templates');
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Create matrix from template
  async createFromTemplate(
    templateId: string,
    name: string,
    description?: string
  ): Promise<CreateRaciMatrixResponse> {
    const params = new URLSearchParams();
    params.append('name', name);
    if (description) params.append('description', description);

    const response = await apiClient.post(
      `/api/v1/raci-matrices/templates/${templateId}?${params.toString()}`
    );
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Bulk assign helper
  async bulkAssign(
    matrixId: string,
    payload: {
      activity_ids: string[];
      role_ids: string[];
      role_type: string;
      notes?: string;
      clear_existing?: boolean;
    }
  ): Promise<{ updated_count: number; warnings: string[] }> {
    const response = await apiClient.post(`/api/v1/raci-matrices/${matrixId}/bulk-assign`, payload);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  }
};

export default raciMatrixService; 
