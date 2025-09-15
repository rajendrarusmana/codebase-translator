# Sidekiq Demo Project

This is a simple Ruby project using Sidekiq for background job processing. It demonstrates:

1. **Image Processing Worker** - Processes images with various operations
2. **Email Notification Worker** - Sends email notifications to users

## Workers

- `ImageProcessingWorker` - Background job for image manipulation
- `EmailNotificationWorker` - Background job for sending emails

## Setup

```bash
bundle install
redis-server  # Start Redis server
```

## Running Workers

```bash
# Start Sidekiq workers
bundle exec sidekiq -r ./config/environment.rb

# Enqueue jobs
ruby lib/enqueue_jobs.rb
```

## Job Types

- **Image Processing**: Resize, crop, filter operations
- **Email Notifications**: Welcome emails, password resets, order confirmations