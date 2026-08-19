# Security policy

Please do not open public issues for vulnerabilities involving malicious PDFs, path handling, dependency compromise, or unintended disclosure of document contents. Use GitHub private vulnerability reporting when the repository is published.

`bidlint` processes untrusted documents. Deployments should isolate document processing, cap file sizes, and avoid forwarding documents to external AI providers unless the operator explicitly enables that behavior.
