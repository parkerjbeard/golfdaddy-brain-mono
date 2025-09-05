"use client"

import * as React from "react"
import { format, subDays, startOfMonth, endOfMonth, subMonths, startOfYear, endOfYear } from "date-fns"
import { Calendar as CalendarIcon } from "lucide-react"
import { DateRange } from "react-day-picker"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

interface DateRangePickerProps extends React.HTMLAttributes<HTMLDivElement> {
  date: DateRange | undefined
  onDateChange: (date: DateRange | undefined) => void
  className?: string
}

export function DateRangePicker({
  date,
  onDateChange,
  className,
  ...divProps
}: DateRangePickerProps) {
  const [open, setOpen] = React.useState(false)
  const handlePreset = (range: DateRange) => {
    onDateChange(range)
    setOpen(false)
  }
  const handleSelect = (range: DateRange | undefined) => {
    onDateChange(range)
    if (range?.from && range?.to) {
      setOpen(false)
    }
  }

  return (
    <div className={cn("grid gap-2", className)} {...divProps}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id="date"
            variant={"outline"}
            className={cn(
              "w-full justify-start text-left font-normal", // Changed w-[300px] to w-full for better flexibility
              !date && "text-muted-foreground"
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            {date?.from ? (
              date.to ? (
                <>
                  {format(date.from, "LLL dd, y")} -{" "}
                  {format(date.to, "LLL dd, y")}
                </>
              ) : (
                format(date.from, "LLL dd, y")
              )
            ) : (
              <span>Pick a date range</span>
            )}
          </Button>
        </PopoverTrigger>
        {/* Compact popover with chip-style quick ranges above calendar */}
        <PopoverContent
          className="min-w-[560px] max-w-[95vw] p-3"
          align="start"
        >
          {(() => {
            const today = new Date()
            const presets: { key: string; label: string; range: DateRange }[] = [
              { key: '7d', label: 'Last 7d', range: { from: subDays(today, 6), to: today } },
              { key: '14d', label: 'Last 14d', range: { from: subDays(today, 13), to: today } },
              { key: '30d', label: 'Last 30d', range: { from: subDays(today, 29), to: today } },
              { key: '90d', label: 'Last 90d', range: { from: subDays(today, 89), to: today } },
              { key: 'tm', label: 'This month', range: { from: startOfMonth(today), to: today } },
              { key: 'lm', label: 'Last month', range: { from: startOfMonth(subMonths(today, 1)), to: endOfMonth(subMonths(today, 1)) } },
              { key: 'ytd', label: 'YTD', range: { from: startOfYear(today), to: today } },
            ]
            return (
              <div className="mb-3 flex flex-wrap gap-2">
                {presets.map((p) => (
                  <Button
                    key={p.key}
                    variant="secondary"
                    size="sm"
                    className="px-2 py-1"
                    onClick={() => handlePreset(p.range)}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            )
          })()}

          <Calendar
            initialFocus
            mode="range"
            defaultMonth={date?.from}
            selected={date}
            onSelect={handleSelect}
            numberOfMonths={2}
            // Minimal caption to reduce clutter
            captionLayout="buttons"
            fromYear={2000}
            toYear={new Date().getFullYear() + 5}
            showOutsideDays
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}
