variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "instance_type" {
  type        = string
  default     = "t3.large" # 2 vCPU / 8 GB. Use c6i.xlarge (4 vCPU / 8 GB) to match the appliance spec.
  description = "EC2 instance type"
}

variable "repo_url" {
  type        = string
  description = "HTTPS URL of the (public) git repository to deploy"
}

variable "domain" {
  type        = string
  default     = ""
  description = "Public hostname (e.g. myname.duckdns.org). Empty = use the IP with a self-signed cert."
}

variable "duckdns_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "ssh_cidr" {
  type        = string
  default     = ""
  description = "CIDR allowed to SSH (e.g. 203.0.113.5/32). Empty = no SSH port."
}

variable "key_name" {
  type        = string
  default     = null
  description = "Existing EC2 key pair name (needed only if you want SSH)"
}
