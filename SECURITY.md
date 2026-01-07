# Security Policy

## Supported Versions

The following versions of FBA-Bench Enterprise are actively supported with security updates:

*   `main` branch (development HEAD)
*   Latest stable release (e.g., vX.Y.Z) - *Specify latest release tag if applicable*

Older versions are not supported and may have unpatched vulnerabilities.

## Reporting a Vulnerability

If you discover a security vulnerability in FBA-Bench Enterprise, please report it to us as soon as possible so that we can address it. We ask that you use the contact information provided below.

**Contact:**
Email: security@fba-bench.com

Please include as much of the following information as possible:
*   The affected version of the project.
*   A detailed description of the vulnerability.
*   Steps to reproduce the vulnerability.
*   Any code or configuration that demonstrates the vulnerability.
*   Your contact information, so we can follow up with you.

We will acknowledge your report within 48 hours and will keep you updated on the progress of the vulnerability.

## Security Best Practices for Users

To ensure the security of your FBA-Bench Enterprise deployment, please follow these best practices:

### Environment Variables and Secrets
*   **Never** commit sensitive information (API keys, database credentials, secrets) directly into the codebase.
*   Use environment variables to configure your application. Avoid hardcoding sensitive values.
*   Ensure that environment variables are securely managed, especially in production environments. Use dedicated secret management tools where appropriate.
*   `SECRET_KEY`: **Always** change this default value to a strong, unique secret in production.
*   Database URLs and API keys should follow best practices for secure storage.

### Dependencies
*   Regularly update your project dependencies to patch known vulnerabilities.
*   Scrutinize third-party libraries before integrating them into your project.

### Access Control
*   Implement appropriate access controls for your deployment.
*   Limit user privileges based on the principle of least privilege.

Refer to the [CONTRIBUTING.md](CONTRIBUTING.md) for information on development environment setup and coding standards.

For broader security guidelines and policies, please refer to [POLICY.md](POLICY.md) (if such a file exists, otherwise remove this line or create it).