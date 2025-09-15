# frozen_string_literal: true

class ImageProcessingWorker
  include Sidekiq::Worker
  sidekiq_options queue: :default, retry: 3, backtrace: true

  # Process an image with the given operations
  # @param image_id [String] the ID of the image to process
  # @param operations [Array<String>] list of operations to apply
  def perform(image_id, operations)
    Rails.logger.info "Starting image processing for image #{image_id}"
    
    # Simulate finding the image in the database
    image = find_image(image_id)
    raise "Image not found: #{image_id}" unless image
    
    # Process the image with the given operations
    processed_image = process_image(image, operations)
    
    # Upload to CDN
    cdn_url = upload_to_cdn(processed_image)
    
    # Update the database record
    update_image_record(image_id, cdn_url)
    
    Rails.logger.info "Completed image processing for image #{image_id}, uploaded to #{cdn_url}"
  rescue StandardError => e
    Rails.logger.error "Failed to process image #{image_id}: #{e.message}"
    raise e
  end

  private

  def find_image(image_id)
    # Simulate database lookup
    {
      id: image_id,
      filename: "photo_#{image_id}.jpg",
      path: "/tmp/images/photo_#{image_id}.jpg",
      metadata: { width: 1920, height: 1080 }
    }
  end

  def process_image(image, operations)
    Rails.logger.info "Processing image #{image[:filename]} with operations: #{operations}"
    
    # Simulate image processing
    processed_data = "processed_#{image[:filename]}"
    operations.each do |operation|
      case operation
      when 'resize'
        processed_data += "_resized"
      when 'crop'
        processed_data += "_cropped"
      when 'filter'
        processed_data += "_filtered"
      end
      sleep(0.1) # Simulate processing time
    end
    
    processed_data
  end

  def upload_to_cdn(processed_image)
    # Simulate CDN upload
    Rails.logger.info "Uploading #{processed_image} to CDN"
    "https://cdn.example.com/images/#{processed_image}"
  end

  def update_image_record(image_id, cdn_url)
    # Simulate database update
    Rails.logger.info "Updating image record #{image_id} with CDN URL: #{cdn_url}"
  end
end