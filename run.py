#!/usr/bin/env python3
"""
InciteRewrite application runner.
Entry point for the legal citation verification system.
"""
import os
from src.app import create_app
from src.citation.courtlistener import init_courtlistener_service

def main():
    """Run the InciteRewrite application."""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Initialize CourtListener service
    api_key = os.environ.get('COURTLISTENER_API_KEY')
    init_courtlistener_service(api_key)
    
    # Create Flask app
    app = create_app()
    
    # Run in development mode
    if os.environ.get('FLASK_CONFIG', 'development') == 'development':
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        # Production mode - should use gunicorn
        print("Use gunicorn for production deployment:")
        print("gunicorn --bind 0.0.0.0:5000 --workers 4 src.app:create_app()")

if __name__ == '__main__':
    main()