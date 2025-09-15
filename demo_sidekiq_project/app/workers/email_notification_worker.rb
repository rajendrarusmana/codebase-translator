# frozen_string_literal: true

class EmailNotificationWorker
  include Sidekiq::Worker
  sidekiq_options queue: :mailers, retry: 5, backtrace: true

  # Send an email notification to a user
  # @param user_id [Integer] the ID of the user to notify
  # @param notification_type [String] the type of notification to send
  # @param data [Hash] additional data for the email template
  def perform(user_id, notification_type, data = {})
    Rails.logger.info "Sending #{notification_type} notification to user #{user_id}"
    
    # Find the user
    user = find_user(user_id)
    raise "User not found: #{user_id}" unless user
    
    # Generate email content
    subject, body = generate_email_content(notification_type, user, data)
    
    # Send the email
    send_email(user[:email], subject, body)
    
    # Log the notification
    log_notification(user_id, notification_type, data)
    
    Rails.logger.info "Successfully sent #{notification_type} notification to #{user[:email]}"
  rescue StandardError => e
    Rails.logger.error "Failed to send #{notification_type} notification to user #{user_id}: #{e.message}"
    raise e
  end

  private

  def find_user(user_id)
    # Simulate database lookup
    {
      id: user_id,
      email: "user#{user_id}@example.com",
      name: "User #{user_id}",
      preferences: { notifications: true }
    }
  end

  def generate_email_content(notification_type, user, data)
    case notification_type
    when 'welcome'
      subject = "Welcome to Our Platform!"
      body = "Hi #{user[:name]}, welcome to our amazing platform!"
    when 'password_reset'
      subject = "Password Reset Request"
      body = "Click here to reset your password: #{data[:reset_url]}"
    when 'order_confirmation'
      subject = "Order Confirmation ##{data[:order_id]}"
      body = "Thank you for your order ##{data[:order_id]}!"
    else
      subject = "Notification"
      body = "You have a new notification."
    end
    
    [subject, body]
  end

  def send_email(email, subject, body)
    # Simulate sending email
    Rails.logger.info "Sending email to #{email}: #{subject}"
    sleep(0.05) # Simulate network delay
  end

  def log_notification(user_id, notification_type, data)
    # Simulate logging
    Rails.logger.info "Logged notification for user #{user_id}: #{notification_type}"
  end
end