#!/usr/bin/env python3
"""
Simple Hello World Script
"""

def main():
    print("=" * 50)
    print("🎉 Welcome to GNN Project!")
    print("=" * 50)
    print("\nHello, World!")
    print("This is a simple Python script uploaded via Claude.\n")
    
    # Get user name
    name = input("What's your name? ")
    print(f"\nNice to meet you, {name}! 👋")
    
    # Simple greeting based on time
    from datetime import datetime
    hour = datetime.now().hour
    
    if hour < 12:
        greeting = "Good morning"
    elif hour < 18:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    
    print(f"{greeting}, {name}!")

if __name__ == "__main__":
    main()
