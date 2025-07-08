import os
import mailerlite as MailerLite

client = MailerLite.Client({
  'api_key': os.getenv("MAILERLITE_API_KEY")
})

print("MailerLite client initialized.", "API Key:", os.getenv("MAILERLITE_API_KEY"), client)