# FPL Darts Game

A multiplayer Premier League Darts game where players compete by selecting footballers based on prompts and using their Premier League appearance counts as darts scores. The game combines football knowledge with classic darts gameplay in a modern web application.

## 🎮 Game Overview

FPL Darts is a unique multiplayer game that merges football trivia with darts scoring:

- **Objective**: Be the first player to reach exactly 0 points from a starting score of 501
- **Gameplay**: Players take turns selecting Premier League footballers based on prompts
- **Scoring**: Each footballer's Premier League appearance count becomes the darts score for that turn
- **Multiplayer**: Create or join game sessions with other players
- **Time Limit**: 60-second time limit per turn to keep games moving

## ✨ Key Features

### 🏆 User Profiles & Statistics
- **User Registration**: Create accounts to track your progress
- **Comprehensive Stats**: Track games played, wins, losses, average scores, and more
- **Achievement System**: Unlock achievements based on performance
- **Game History**: View your last 10 games with detailed results
- **Performance Metrics**: Best/worst scores, perfect games, and forfeit tracking

### 🎯 Game Mechanics
- **Dynamic Prompts**: Footballer selection based on various criteria (clubs, positions, countries, etc.)
- **Real-time Multiplayer**: Join game sessions with other players
- **Session Management**: Create private game sessions with unique codes
- **Turn-based Play**: Structured gameplay with automatic turn progression
- **Forfeit System**: Players can forfeit turns if they can't find a valid player

### 🎨 Modern Web Interface
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: Live game state updates without page refresh
- **Player Search**: Search through thousands of Premier League players
- **Game Lobby**: Browse and join available game sessions
- **Profile Dashboard**: Comprehensive view of your gaming statistics

## 🚀 Deployment Options

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
├── app.py                 # Main Flask application with all routes and game logic
├── players_pl.json        # Comprehensive Premier League player database
├── users.json             # User profiles and statistics storage
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment configuration
├── Procfile              # Heroku deployment configuration
├── runtime.txt           # Python version specification
├── templates/
│   ├── index.html        # Main game interface
│   ├── lobby.html        # Game session browser
│   ├── login.html        # User authentication
│   └── profile.html      # User statistics dashboard
├── TODO                  # Planned features and improvements
└── README.md             # This file
```

## 🎮 How to Play

### Getting Started
1. **Register/Login**: Create an account or log in to track your progress
2. **Join or Create**: Enter the lobby to join existing games or create a new session
3. **Game Setup**: Share your session code with friends or wait for players to join

### Gameplay Rules
1. **Starting Score**: Each player begins with 501 points
2. **Turn Structure**: Players take turns selecting footballers based on prompts
3. **Scoring**: The selected player's Premier League appearances become your dart score
4. **Winning**: First player to reach exactly 0 points wins
5. **Bust Rule**: Going below -20 results in a bust (score resets to previous value)
6. **Time Limit**: 60 seconds per turn to maintain game pace

### Example Turn
- **Prompt**: "Select a player who played for Manchester United"
- **Player Choice**: Ryan Giggs (632 Premier League appearances)
- **Score**: 632 points deducted from your total
- **Result**: If you had 501 points, you now have -131 (bust!)

## 🔧 Local Development

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/fpl-darts-game.git
   cd fpl-darts-game
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Access the application:**
   ```
   http://localhost:5000
   ```

## 📊 Data Sources

The game uses a comprehensive database of Premier League players including:
- **Player Names**: Full names of all Premier League players
- **Appearance Counts**: Total Premier League appearances for each player
- **Club History**: All clubs each player has represented
- **Positions**: Player positions (GK, DF, MF, FW)
- **Nationalities**: Player countries of origin

## 🌐 Environment Variables

No environment variables are required for basic deployment. The application uses:
- Local file storage for user profiles (`users.json`)
- Local file storage for player data (`players_pl.json`)
- In-memory session storage for active games

## 🔮 Planned Features

- **Leaderboard System**: Global and session-based leaderboards
- **Enhanced Prompts**: Improved prompt generation with minimum valid answer requirements
- **Real-time Chat**: In-game communication between players
- **Tournament Mode**: Organized competitions with brackets
- **Mobile App**: Native mobile application

## 🆘 Troubleshooting

### Common Issues

**Port binding errors:**
- Free tiers often use different ports
- Check deployment platform logs for correct port

**Memory limits:**
- Free tiers have memory restrictions
- Consider upgrading for production use

**Cold starts:**
- Free tiers may have slower initial load times
- This is normal for free hosting services

### Solutions

1. **Check deployment logs** for specific error messages
2. **Verify all files** are committed to your repository
3. **Ensure requirements.txt** includes all dependencies
4. **Check file permissions** for JSON data files

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for:
- Bug fixes
- New features
- Documentation improvements
- Performance optimizations

## 📝 License

This project is open source and available under the MIT License.

## 🎯 Game Statistics

The application tracks comprehensive player statistics including:
- Games played, won, and lost
- Average scores and best/worst performances
- Turn efficiency and forfeit rates
- Perfect games (winning with exactly 0 points)
- Recent game history with opponent information
