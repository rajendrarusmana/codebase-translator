# frozen_string_literal: true

# Environment setup for the Sidekiq demo
require 'bundler/setup'
require 'sidekiq'

# Configure Sidekiq
Sidekiq.configure_server do |config|
  config.redis = { url: 'redis://localhost:6379/0' }
end

Sidekiq.configure_client do |config|
  config.redis = { url: 'redis://localhost:6379/0' }
end

# Load worker classes
Dir[File.join(File.dirname(__FILE__), '../app/workers/*.rb')].each { |file| require file }