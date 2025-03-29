# Load environment variables from .env file
$envVars = Get-Content -Path .env | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+?)\s*=\s*(.+?)\s*$") {
        $name, $value = $matches[1], $matches[2]
        [System.Environment]::SetEnvironmentVariable($name, $value)
        @{ Name = $name; Value = $value }
    }
}

# Submit the build
gcloud builds submit --tag gcr.io/$env:PROJECT_ID/$env:SERVICE_NAME

# Deploy to Google Cloud Run
gcloud run deploy $env:SERVICE_NAME `
    --image gcr.io/$env:PROJECT_ID/$env:SERVICE_NAME `
    --platform managed `
    --memory 512Mi `
    --allow-unauthenticated `
    --set-env-vars PROJECT_ID=$env:PROJECT_ID `
    --set-env-vars SERVICE_NAME=$env:SERVICE_NAME `
    --set-env-vars TELEGRAM_BOT_TOKEN=$env:TELEGRAM_BOT_TOKEN `
    --set-env-vars SPREADSHEET_ID=$env:SPREADSHEET_ID `
    --set-env-vars CHANNEL_USERNAME=$env:CHANNEL_USERNAME `
    --set-env-vars TOPIC_THREAD_ID=$env:TOPIC_THREAD_ID `
    --set-env-vars CLOUD_RUN_URL=$env:CLOUD_RUN_URL `
    --set-env-vars GOOGLE_CREDENTIALS_JSON=$env:GOOGLE_CREDENTIALS_JSON

# Describe the service to get the URL
$serviceUrl = gcloud run services describe $env:SERVICE_NAME --format="value(status.url)"
Write-Output "Service URL: $serviceUrl"

# Set the Telegram Webhook
Invoke-RestMethod -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/setWebhook?url=$serviceUrl/$env:TELEGRAM_BOT_TOKEN" -Method Post

# Add or Update UptimeRobot Monitor
Invoke-RestMethod -Uri 'https://api.uptimerobot.com/v2/newMonitor' -Method Post -Body (@{ 
    api_key=$env:UPTIMEROBOT_API_KEY; 
    format='json'; 
    type='1'; 
    url="$serviceUrl/health"; 
    friendly_name='NTUTC Shed Bot'; 
    interval='300' 
} | ConvertTo-Json) -ContentType 'application/json'