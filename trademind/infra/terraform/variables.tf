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
  description = <<-EOT
    Monthly AWS budget; alert at 80% of forecast. The owner's ceiling is Rs 10,000 a month for everything
    (AWS, Claude plan, Kite Connect), so AWS gets about $45: server ~$23, Bedrock research notes $15,
    and the agent's Bedrock fallback, which is off by default (docs/AGENT.md).
  EOT
  type        = number
  default     = 45
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

variable "agent_bedrock_monthly_usd" {
  description = "Bedrock fallback for the ops agent, USD per month. 0 (default) gives the agent role no Bedrock access."
  type        = number
  default     = 0
}

variable "research_bedrock_monthly_usd" {
  description = "The research notes' own Bedrock cap (settings.yaml research.monthly_budget_usd)."
  type        = number
  default     = 15
}
