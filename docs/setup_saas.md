# SaaS setup

## Option A: Terraform (AWS)
```bash
cd terraform
terraform init
terraform apply -var repo_url=https://github.com/<you>/<repo>.git \
                -var domain=<name>.duckdns.org -var duckdns_token=<token>
terraform output url
terraform output -raw admin_password
```
Creates one EC2 instance (Ubuntu 22.04, 40 GB), an Elastic IP and a security group (80, 443, 514; SSH only if
`ssh_cidr` is set). `user_data` installs Docker, clones the repo, writes `.env` with random passwords and runs `make up`.
Caddy obtains a Let's Encrypt certificate for `domain`; without a domain you get a self-signed certificate on the IP.
Passwords live in the Terraform state and EC2 user-data — keep the state private.

## Option B: any VM
Follow `setup_appliance.md` and set `DOMAIN=<your hostname>` in `.env` (DNS must point at the VM; open 80/443).

## CI/CD
`.github/workflows/ci.yml` runs the tests against a Postgres service and builds the images on every push.
`deploy.yml` (manual) pulls `main` on the VM over SSH (secrets `DEPLOY_HOST`, `DEPLOY_SSH_KEY`).
