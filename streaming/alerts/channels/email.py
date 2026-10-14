"""Email notification channel utilizing standard library SMTP.

Delivers formatted alert notifications to designated operational recipient
email addresses with configurable server connection parameters and strict
payload minimization excluding raw telemetry metrics and cell identities.
"""
