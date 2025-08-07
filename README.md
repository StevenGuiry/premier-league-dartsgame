# FPL Darts Game

A Premier League Darts game where players select footballers based on prompts and use their appearance counts as darts scores.

## 🚀 Free Hosting Options

### Option 1: Render (Recommended)

1. **Create a GitHub repository:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/fpl-darts-game.git
   git push -u origin main
   ```

2. **Deploy on Render:**
   - Go to [render.com](https://render.com) and sign up
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will automatically detect it's a Python app
   - Click "Create Web Service"
   - Your app will be live at `https://your-app-name.onrender.com`

### Option 2: Railway

1. **Deploy on Railway:**
   - Go to [railway.app](https://railway.app) and sign up
   - Click "New Project" → "Deploy from GitHub repo"
   - Connect your repository
   - Railway will automatically deploy your app
   - Get your live URL from the dashboard

### Option 3: Heroku

1. **Install Heroku CLI:**
   ```bash
   # Download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Deploy:**
   ```bash
   heroku login
   heroku create your-app-name
   git push heroku main
   heroku open
   ```

### Option 4: PythonAnywhere

1. **Sign up at [pythonanywhere.com](https://pythonanywhere.com)**
2. **Upload your files via the Files tab**
3. **Create a new web app:**
   - Go to Web tab
   - Click "Add a new web app"
   - Choose "Flask" and Python 3.9
   - Set the source code directory
   - Configure WSGI file to point to your app

## 📁 Project Structure

```
FPL_Darts_Python/
├── app.py                 # Main Flask application
├── players_pl.json        # Player data
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── Procfile              # Heroku deployment config
├── runtime.txt           # Python version specification
├── templates/
│   └── index.html        # Frontend template
└── README.md             # This file
```

## 🎮 How to Play

1. Each player starts with 501 points
2. Players take turns selecting footballers based on prompts
3. The footballer's appearance count becomes the darts score
4. First player to reach 0 (or closest to 0 without going below -20) wins
5. Each turn has a 60-second time limit

## 🔧 Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the app:**
   ```bash
   python app.py
   ```

3. **Open in browser:**
   ```
   http://localhost:5000
   ```

## 🌐 Environment Variables

No environment variables are required for basic deployment. The app uses local file storage for player data.

## 📝 Notes

- The app uses `players_pl.json` for player data
- All game state is stored in memory (resets on server restart)
- The free tiers may have limitations on concurrent users
- Consider upgrading to paid tiers for production use

## 🆘 Troubleshooting

**Common Issues:**
- **Port binding errors:** Free tiers often use different ports
- **Memory limits:** Free tiers have memory restrictions
- **Cold starts:** Free tiers may have slower initial load times

**Solutions:**
- Check the deployment platform's logs for errors
- Ensure all files are committed to your repository
- Verify the `requirements.txt` includes all dependencies
