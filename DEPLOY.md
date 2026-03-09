# Deployment Guide

## Option 1: PythonAnywhere (Recommended - Free)

1. **Create Account:**
   - Go to https://www.pythonanywhere.com/
   - Sign up for a free account

2. **Upload Files:**
   - Go to "Files" tab
   - Upload all project files (app.py, templates/, static/, instance/)

3. **Set up Web App:**
   - Go to "Web" tab
   - Click "Add a new web app"
   - Choose "Flask" and Python version
   - Set the WSGI configuration file path

4. **Configure WSGI:**
   - Click on the WSGI configuration file link
   - Replace content with:
   ```python
   import sys
   path = '/home/yourusername/'
   if path not in sys.path:
       sys.path.insert(0, path)
   
   from app import app as application
   ```

5. **Install Dependencies:**
   - Go to "Consoles" tab
   - Run: pip install flask werkzeug gunicorn

6. **Access Your App:**
   - Your app will be at: https://yourusername.pythonanywhere.com

---

## Option 2: Render (Free)

1. **Create Account:**
   - Go to https://render.com/
   - Sign up with GitHub

2. **Create Web Service:**
   - New → Web Service
   - Connect your GitHub repository or upload files

3. **Configure:**
   - Build Command: (leave empty)
   - Start Command: gunicorn app:app

4. **Access Your App:**
   - Get your public URL from Render dashboard

---

## Option 3: Railway (Free)

1. **Create Account:**
   - Go to https://railway.app/
   - Sign up with GitHub

2. **Deploy:**
   - New → GitHub Repo
   - Select your repository

3. **Environment:**
   - Add PORT variable = 8000

4. **Access Your App:**
   - Get your public URL from Railway dashboard

---

## Option 4: Local Network (Already Running)

Your app is currently running at:
- Computer: http://localhost:5000
- Mobile (same WiFi): http://10.69.50.92:5000

