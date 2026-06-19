# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | ✅ Yes    |

## Reporting a Vulnerability

If you discover a security vulnerability in autoresearch, please report 
it responsibly by using GitHub's private security advisory feature:

👉 **[Report a vulnerability](https://github.com/Code7unner/autoresearch/security/advisories/new)**

Please do NOT open a public GitHub issue for security vulnerabilities.

## What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact
- Suggested fix (if any)

## Response Timeline

- Acknowledgement within **48 hours**
- Status update within **7 days**
- Fix timeline communicated within **14 days**

## Scope

The following are considered in scope:
- Authentication and authorization bypass
- Remote code execution
- Path traversal / arbitrary file read
- Server-Side Request Forgery (SSRF)
- Injection vulnerabilities (SQL, command, prompt)
- Sensitive data exposure

## Out of Scope

- Vulnerabilities in dependencies (report to the dependency maintainer)
- Social engineering attacks
- Denial of service via resource exhaustion

## Handling Credentials

When configuring credentials (Twitter/XHS cookies, GitHub/Groq tokens, proxy URLs),
prefer `--stdin` or `--file PATH` over passing the secret as a command-line argument:

```bash
pbpaste | autoresearch configure twitter-cookies --stdin
autoresearch configure github-token --file ~/secrets/gh-token.txt
```

Command-line arguments are visible in your shell history and to any process that can
read `ps`. `configure` warns when a credential key is passed on argv.

## Credits

We appreciate responsible disclosure and will credit researchers 
in our release notes unless anonymity is requested.
