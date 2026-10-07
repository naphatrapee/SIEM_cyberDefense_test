output "public_ip" {
  value = aws_eip.logdemo.public_ip
}

output "url" {
  value = var.domain != "" ? "https://${var.domain}" : "https://${aws_eip.logdemo.public_ip} (self-signed certificate)"
}

output "admin_password" {
  value     = random_password.admin.result
  sensitive = true
}

output "viewer_password" {
  value     = random_password.viewer.result
  sensitive = true
}
