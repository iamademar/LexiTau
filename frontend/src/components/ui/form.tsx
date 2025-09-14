import * as React from "react"
import { cn } from "@/lib/utils"
import { Label } from "./label"

interface FormItemProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

type FormLabelProps = React.ComponentPropsWithoutRef<typeof Label>

interface FormControlProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

interface FormDescriptionProps extends React.HTMLAttributes<HTMLParagraphElement> {
  children: React.ReactNode
}

interface FormMessageProps extends React.HTMLAttributes<HTMLParagraphElement> {
  children?: React.ReactNode
}

interface FormFieldProps {
  name: string
  children: React.ReactNode
  error?: string
}

const FormItem = React.forwardRef<HTMLDivElement, FormItemProps>(
  ({ className, ...props }, ref) => {
    return (
      <div ref={ref} className={cn("space-y-2", className)} {...props} />
    )
  }
)
FormItem.displayName = "FormItem"

const FormLabel = React.forwardRef<
  React.ElementRef<typeof Label>,
  FormLabelProps
>(({ className, ...props }, ref) => {
  return (
    <Label
      ref={ref}
      className={cn("data-[error=true]:text-destructive", className)}
      {...props}
    />
  )
})
FormLabel.displayName = "FormLabel"

const FormControl = React.forwardRef<HTMLDivElement, FormControlProps>(
  ({ ...props }, ref) => {
    return (
      <div ref={ref} {...props} />
    )
  }
)
FormControl.displayName = "FormControl"

const FormDescription = React.forwardRef<HTMLParagraphElement, FormDescriptionProps>(
  ({ className, ...props }, ref) => {
    return (
      <p
        ref={ref}
        className={cn("text-sm text-muted-foreground", className)}
        {...props}
      />
    )
  }
)
FormDescription.displayName = "FormDescription"

const FormMessage = React.forwardRef<HTMLParagraphElement, FormMessageProps>(
  ({ className, children, ...props }, ref) => {
    if (!children) {
      return null
    }

    return (
      <p
        ref={ref}
        className={cn("text-sm font-medium text-destructive", className)}
        {...props}
      >
        {children}
      </p>
    )
  }
)
FormMessage.displayName = "FormMessage"

const FormField: React.FC<FormFieldProps> = ({ name, children, error }) => {
  return (
    <FormItem>
      {children}
      {error && (
        <FormMessage id={`${name}-error`}>
          {error}
        </FormMessage>
      )}
    </FormItem>
  )
}

export {
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
  FormField,
}
