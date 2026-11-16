variable "region" {
  description = "AWS region. Mumbai is closest to the exchange."
  type        = string
  default     = "ap-south-1"
}

variable "instance_type" {
  description = "ARM64 (Graviton) instance. t4g.medium = 2 vCPU, 4 GiB."
  type        = string
  default     = "t4g.medium"
}

variable "alert_email" {
  description = "Email for health alarms and the monthly budget alert."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly AWS budget; alert at 80% of forecast. Blueprint ceiling is about Rs 10,000."
  type        = number
  default     = 110
}
