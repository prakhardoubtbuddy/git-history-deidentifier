import re
# git-filter-repo --blob-callback body.
# Redacts common live-credential FORMATS by pattern (value-independent), so any
# real key of a known provider is neutralised even if a literal-match list missed it.
# Newline counts are preserved (multi-line keys padded) so line-based metrics (LOC)
# are unchanged by redaction.
d = blob.data
_markers = (b'PRIVATE KEY', b'sk-ant-', b'sk-proj-', b'sk-', b'EAAA', b'AKIA',
            b'AIza', b'ghp_', b'gho_', b'ghu_', b'ghs_', b'ghr_', b'xox',
            b'_live_', b'eyJ', b'SK', b'AC')
if any(m in d for m in _markers):
    def pad(m):
        return b'REDACTED_PRIVATE_KEY' + b'\n' * m.group(0).count(b'\n')
    d = re.sub(rb'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----', pad, d, flags=re.DOTALL)
    d = re.sub(rb'sk-ant-[A-Za-z0-9_\-]{20,}', b'REDACTED_ANTHROPIC_KEY', d)
    d = re.sub(rb'sk-proj-[A-Za-z0-9_\-]{20,}', b'REDACTED_OPENAI_KEY', d)
    d = re.sub(rb'sk-[A-Za-z0-9]{32,}', b'REDACTED_OPENAI_KEY', d)
    d = re.sub(rb'EAAA[A-Za-z0-9_\-]{20,}', b'REDACTED_SQUARE_TOKEN', d)
    d = re.sub(rb'AKIA[0-9A-Z]{16}', b'REDACTED_AWS_KEY', d)
    d = re.sub(rb'AIza[0-9A-Za-z_\-]{35}', b'REDACTED_GOOGLE_KEY', d)
    d = re.sub(rb'gh[pousr]_[A-Za-z0-9]{36,}', b'REDACTED_GITHUB_TOKEN', d)
    d = re.sub(rb'xox[baprs]-[A-Za-z0-9\-]{10,}', b'REDACTED_SLACK_TOKEN', d)
    d = re.sub(rb'(?:sk|rk)_live_[A-Za-z0-9]{20,}', b'REDACTED_STRIPE_KEY', d)
    d = re.sub(rb'SK[0-9a-fA-F]{32}', b'REDACTED_TWILIO_SID', d)
    d = re.sub(rb'AC[0-9a-fA-F]{32}', b'REDACTED_TWILIO_ACCOUNT', d)
    d = re.sub(rb'eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}', b'REDACTED_JWT', d)
    blob.data = d
