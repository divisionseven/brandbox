# Security Policy

## Supported Versions

We release patches for security vulnerabilities. The following versions are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**Please DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via:

[GitHub's Security Advisories](https://github.com/divisionseven/brandbox/security/advisories/new) feature. This allows us to discuss and fix the issue privately before disclosure.

### What to Include

When reporting, please include:

- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact of the vulnerability
- Any possible fixes or mitigations (if known)

### Response Timeline

We aim to acknowledge vulnerability reports within **48 hours** and provide a timeline for the fix within **7 days**.

- Acknowledgment: Within 48 hours
- Initial assessment: Within 7 days
- Fix timeline: Depends on severity (critical issues prioritized)

## Security Best Practices

When using brandbox:

1. **Input validation**: Only process images from trusted sources
2. **File size limits**: Be cautious when processing very large images
3. **Sandboxed environments**: Consider running in isolated environments for untrusted inputs

## Scope

This security policy applies to:
- The `brandbox` CLI tool
- All official distribution channels (PyPI, GitHub releases)

This policy does NOT cover:
- Third-party modifications or forks
- Unofficial distribution channels
- User-generated content processed by the tool

## Disclosure Policy

We follow a **coordinated disclosure** process:
1. Reporter notifies us privately
2. We develop and test a fix
3. We coordinate on disclosure timing
4. Public release with credit to reporter (unless requested otherwise)

## Credit

We believe in recognizing responsible security researchers. With your permission, we will acknowledge your contribution in the release notes and security advisory.
