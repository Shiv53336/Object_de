output "instance_id" {
  value = aws_instance.trademind.id
}

output "static_ip" {
  description = "Stable egress IP. Whitelist this in Kite only when live orders are approved (Phase 14)."
  value       = aws_eip.trademind.public_ip
}

output "backup_bucket" {
  value = aws_s3_bucket.backup.bucket
}

output "connect" {
  value = "aws ssm start-session --target ${aws_instance.trademind.id} --region ${var.region}"
}

output "api_tunnel" {
  description = "Forward the read-only API to your laptop on port 8000."
  value       = "aws ssm start-session --target ${aws_instance.trademind.id} --region ${var.region} --document-name AWS-StartPortForwardingSession --parameters portNumber=8000,localPortNumber=8000"
}
