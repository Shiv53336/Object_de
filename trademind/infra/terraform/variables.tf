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

variable "github_repo" {
  description = "owner/name of the GitHub repository whose trademind-agent workflow may assume the agent role."
  type        = string
  default     = "Shiv53336/Object_de"
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub Actions OIDC provider. Set false if the account already has one."
  type        = bool
  default     = true
}
