import logging
import random
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
ADMINS = [123456789, 987654321]  # Replace with your Telegram user IDs
TOURNAMENTS_FILE = 'data/tournaments.json'
TEAMS_FILE = 'data/teams.json'
DATA_DIR = 'data'
ROSTERS_DIR = 'rosters'

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ROSTERS_DIR, exist_ok=True)

def load_data(filename):
    """Load data from JSON file"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data, filename):
    """Save data to JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving data: {e}")
        return False

# Load existing data
tournaments = load_data(TOURNAMENTS_FILE)
teams = load_data(TEAMS_FILE)
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with main menu"""
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🏆 Tournaments", callback_data="view_tournaments")],
        [InlineKeyboardButton("👥 View Teams", callback_data="view_teams")],
    ]
    
    if user_id in ADMINS:
        keyboard.append([InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            "🤖 Welcome to Brawl Stars Tournament Bot!\n\n"
            "Join tournaments, view teams, and compete!",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            "🤖 Welcome to Brawl Stars Tournament Bot!\n\n"
            "Join tournaments, view teams, and compete!",
            reply_markup=reply_markup
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    handlers = {
        "view_tournaments": show_tournaments,
        "view_teams": show_teams_list,
        "admin_panel": admin_panel,
        "main_menu": start
    }
    
    if data in handlers:
        await handlers[data](query, context)
    elif data.startswith("tournament_"):
        tournament_id = data.split("_")[1]
        await join_tournament_start(query, context, tournament_id)
    elif data.startswith("view_teams_"):
        tournament_id = data.split("_")[2]
        await show_tournament_teams(query, context, tournament_id)
    elif data.startswith("team_details_"):
        team_id = data.split("_")[2]
        await show_team_details(query, context, team_id)
    elif data.startswith("admin_delete_team_"):
        tournament_id = data.split("_")[3]
        await admin_delete_team_menu(query, context, tournament_id)
    elif data.startswith("confirm_delete_team_"):
        team_id = data.split("_")[3]
        await admin_delete_team_confirm(query, context, team_id)
    elif data.startswith("admin_delete_tournament_"):
        tournament_id = data.split("_")[3]
        await admin_delete_tournament_menu(query, context)
    elif data.startswith("confirm_delete_tournament_"):
        tournament_id = data.split("_")[3]
        await admin_delete_tournament_confirm(query, context, tournament_id)
    elif data.startswith("report_winner_"):
        parts = data.split("_")
        match_id = parts[2]
        winner_team_id = parts[3]
        await report_match_winner(query, context, match_id, winner_team_id)

async def show_tournaments(query, context):
    """Show available tournaments"""
    active_tournaments = {k: v for k, v in tournaments.items() if v['status'] == 'active'}
    
    if not active_tournaments:
        await query.edit_message_text("No active tournaments available. Check back later!")
        return
    
    keyboard = []
    for tournament_id, tournament in active_tournaments.items():
        teams_count = len([t for t in teams.values() if t.get('tournament_id') == tournament_id])
        button_text = f"{tournament['name']} ({teams_count}/{tournament['max_teams']})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"tournament_{tournament_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🏆 Available Tournaments:", reply_markup=reply_markup)

async def join_tournament_start(query, context, tournament_id):
    """Start team registration process"""
    if tournament_id not in tournaments:
        await query.edit_message_text("❌ Tournament not found!")
        return
    
    tournament = tournaments[tournament_id]
    teams_count = len([t for t in teams.values() if t.get('tournament_id') == tournament_id])
    
    if teams_count >= tournament['max_teams']:
        await query.edit_message_text("❌ This tournament is full!")
        return
    
    user_id = query.from_user.id
    user_states[user_id] = {'state': 'waiting_team_name', 'tournament_id': tournament_id}
    
    await query.edit_message_text(
        f"Joining: {tournament['name']}\n\n"
        "Please enter your team name:"
    )

async def handle_team_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle team name input"""
    user_id = update.effective_user.id
    if user_id not in user_states or user_states[user_id].get('state') != 'waiting_team_name':
        return
    
    team_name = update.message.text.strip()
    if not team_name:
        await update.message.reply_text("Please enter a valid team name:")
        return
    
    tournament_id = user_states[user_id]['tournament_id']
    
    # Check if team name already exists
    existing_teams = [t for t in teams.values() if t.get('tournament_id') == tournament_id and t.get('name', '').lower() == team_name.lower()]
    if existing_teams:
        await update.message.reply_text("❌ Team name already exists in this tournament. Please choose a different name:")
        return
    
    user_states[user_id] = {
        'state': 'waiting_leader_username', 
        'tournament_id': tournament_id,
        'team_name': team_name
    }
    
    await update.message.reply_text("👑 Please enter team leader's username (for contact, without @):")

async def handle_leader_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle leader username input"""
    user_id = update.effective_user.id
    if user_id not in user_states or user_states[user_id].get('state') != 'waiting_leader_username':
        return
    
    leader_username = update.message.text.strip().lstrip('@')
    if not leader_username:
        await update.message.reply_text("Please enter a valid username:")
        return
    
    tournament_id = user_states[user_id]['tournament_id']
    team_name = user_states[user_id]['team_name']
    
    user_states[user_id] = {
        'state': 'waiting_roster', 
        'tournament_id': tournament_id,
        'team_name': team_name,
        'leader_username': leader_username,
        'roster_photos': []
    }
    
    await update.message.reply_text("📸 Please send 3 roster photos (send them one by one):")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle roster photo uploads"""
    user_id = update.effective_user.id
    if user_id not in user_states or user_states[user_id].get('state') != 'waiting_roster':
        return
    
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    
    # Save photo
    photo_id = f"photo_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    photo_path = os.path.join(ROSTERS_DIR, photo_id)
    await photo_file.download_to_drive(photo_path)
    
    user_states[user_id]['roster_photos'].append(photo_id)
    
    if len(user_states[user_id]['roster_photos']) >= 3:
        await finish_team_registration(update, context, user_id)
    else:
        remaining = 3 - len(user_states[user_id]['roster_photos'])
        await update.message.reply_text(f"✅ Photo received! Send {remaining} more photo(s).")

async def finish_team_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Complete team registration"""
    user_data = user_states[user_id]
    tournament_id = user_data['tournament_id']
    
    # Create team
    team_id = f"team_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    teams[team_id] = {
        'id': team_id,
        'name': user_data['team_name'],
        'leader_username': user_data['leader_username'],
        'tournament_id': tournament_id,
        'roster_photos': user_data['roster_photos'],
        'registered_by': user_id,
        'status': 'active'
    }
    
    save_data(teams, TEAMS_FILE)
    
    # Notify admins
    tournament = tournaments[tournament_id]
    teams_count = len([t for t in teams.values() if t.get('tournament_id') == tournament_id])
    
    admin_text = (
        f"🆕 New team registered!\n"
        f"Tournament: {tournament['name']}\n"
        f"Team: {user_data['team_name']}\n"
        f"Leader: @{user_data['leader_username']}\n"
        f"Total teams: {teams_count}/{tournament['max_teams']}"
    )
    
    await notify_admins(context, admin_text)
    await send_teams_list_to_admins(context, tournament_id)
    
    # Check if tournament is full
    if teams_count >= tournament['max_teams']:
        tournaments[tournament_id]['status'] = 'full'
        save_data(tournaments, TOURNAMENTS_FILE)
        await notify_admins(context, f"🎯 Tournament {tournament['name']} is now FULL!")
    
    del user_states[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🏆 View Tournaments", callback_data="view_tournaments")],
        [InlineKeyboardButton("👥 View Teams", callback_data="view_teams")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Team registered successfully!\n\n"
        f"Team: {user_data['team_name']}\n"
        f"Leader: @{user_data['leader_username']}\n\n"
        "Good luck in the tournament! 🎮",
        reply_markup=reply_markup
    )

async def show_teams_list(query, context):
    """Show list of tournaments with teams"""
    active_tournaments = {k: v for k, v in tournaments.items() if v['status'] in ['active', 'full', 'started']}
    
    if not active_tournaments:
        await query.edit_message_text("No tournaments with teams available.")
        return
    
    keyboard = []
    for tournament_id, tournament in active_tournaments.items():
        tournament_teams = [t for t in teams.values() if t.get('tournament_id') == tournament_id]
        if tournament_teams:
            button_text = f"{tournament['name']} ({len(tournament_teams)} teams)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"view_teams_{tournament_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Select tournament to view teams:", reply_markup=reply_markup)

async def show_tournament_teams(query, context, tournament_id):
    """Show teams for a specific tournament"""
    tournament_teams = [t for t in teams.values() if t.get('tournament_id') == tournament_id and t.get('status') == 'active']
    
    if not tournament_teams:
        await query.edit_message_text("No teams registered for this tournament yet.")
        return
    
    keyboard = []
    for team in tournament_teams:
        keyboard.append([InlineKeyboardButton(
            f"{team['name']} (@{team['leader_username']})", 
            callback_data=f"team_details_{team['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="view_teams")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Teams in {tournaments[tournament_id]['name']}:", reply_markup=reply_markup)

async def show_team_details(query, context, team_id):
    """Show team details and roster"""
    if team_id not in teams:
        await query.edit_message_text("❌ Team not found!")
        return
    
    team = teams[team_id]
    tournament = tournaments.get(team['tournament_id'], {})
    
    text = (
        f"🏆 {team['name']}\n"
        f"Tournament: {tournament.get('name', 'Unknown')}\n"
        f"Leader: @{team['leader_username']}\n\n"
        f"Roster Photos:"
    )
    
    await query.edit_message_text(text)
    
    # Send roster photos
    for photo_name in team.get('roster_photos', []):
        photo_path = os.path.join(ROSTERS_DIR, photo_name)
        try:
            with open(photo_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=InputFile(photo),
                    caption=f"{team['name']} Roster"
                )
        except FileNotFoundError:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Roster photo not available"
            )

# Admin functions
async def admin_panel(query, context):
    """Show admin panel"""
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("❌ Admin access required!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Create Tournament", callback_data="create_tournament_dialog")],
        [InlineKeyboardButton("🗑️ Delete Tournament", callback_data="admin_delete_tournament_menu")],
        [InlineKeyboardButton("👥 Manage Teams", callback_data="admin_manage_teams")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🔧 Admin Panel", reply_markup=reply_markup)

async def admin_manage_teams(query, context):
    """Show tournaments for team management"""
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("❌ Admin access required!")
        return
    
    active_tournaments = {k: v for k, v in tournaments.items() if v['status'] in ['active', 'full', 'started']}
    
    if not active_tournaments:
        await query.edit_message_text("No tournaments available for management.")
        return
    
    keyboard = []
    for tournament_id, tournament in active_tournaments.items():
        tournament_teams = [t for t in teams.values() if t.get('tournament_id') == tournament_id]
        button_text = f"{tournament['name']} ({len(tournament_teams)} teams)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_delete_team_{tournament_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Select tournament to manage teams:", reply_markup=reply_markup)

async def admin_delete_team_menu(query, context, tournament_id):
    """Show teams for deletion"""
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("❌ Admin access required!")
        return
    
    tournament_teams = [t for t in teams.values() if t.get('tournament_id') == tournament_id and t.get('status') == 'active']
    
    if not tournament_teams:
        await query.edit_message_text("No teams to delete.")
        return
    
    keyboard = []
    for team in tournament_teams:
        keyboard.append([InlineKeyboardButton(
            f"❌ {team['name']} (@{team['leader_username']})", 
            callback_data=f"confirm_delete_team_{team['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_manage_teams")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Select team to delete:", reply_markup=reply_markup)

async def admin_delete_team_confirm(query, context, team_id):
    """Confirm and delete team"""
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("❌ Admin access required!")
        return
    
    if team_id in teams:
        team_name = teams[team_id]['name']
        del teams[team_id]
        save_data(teams, TEAMS_FILE)
        await query.edit_message_text(f"✅ Team '{team_name}' deleted successfully!")
    else:
        await query.edit_message_text("❌ Team not found!")

async def admin_delete_tournament_menu(query, context):
    """Show tournaments for deletion"""
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("❌ Admin access required!")
        return
    
    if not tournaments:
        await query.edit_message_text("No tournaments to delete.")
        return
    
    keyboard = []
    for tournament_id, tournament in tournaments.items():
        keyboard.append([InlineKeyboardButton(
            f"❌ {tournament['name']}", 
            callback_data=f"confirm_delete_tournament_{tournament_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Select tournament to delete:", reply_markup=reply_markup)

async def admin_delete_tournament_confirm(query, context, tournament_id):
    """Confirm and delete tournament"""
    if query.from_user.id not in ADMINS:
        await query.edit_message_text("❌ Admin access required!")
        return
    
    if tournament_id in tournaments:
        tournament_name = tournaments[tournament_id]['name']
        
        # Remove teams from this tournament
        teams_to_delete = [team_id for team_id, team in teams.items() if team.get('tournament_id') == tournament_id]
        for team_id in teams_to_delete:
            del teams[team_id]
        
        del tournaments[tournament_id]
        save_data(tournaments, TOURNAMENTS_FILE)
        save_data(teams, TEAMS_FILE)
        
        await query.edit_message_text(f"✅ Tournament '{tournament_name}' deleted successfully!")
    else:
        await query.edit_message_text("❌ Tournament not found!")

async def notify_admins(context, message):
    """Send notification to all admins"""
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(admin_id, message)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

async def send_teams_list_to_admins(context, tournament_id):
    """Send teams list to admins"""
    tournament_teams = [t for t in teams.values() if t.get('tournament_id') == tournament_id and t.get('status') == 'active']
    tournament = tournaments[tournament_id]
    
    text = f"👥 Teams in {tournament['name']}:\n\n"
    for i, team in enumerate(tournament_teams, 1):
        text += f"{i}. {team['name']} (@{team['leader_username']})\n"
    
    text += f"\nTotal: {len(tournament_teams)}/{tournament['max_teams']}"
    await notify_admins(context, text)

# Command handlers
async def create_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new tournament - /create <name> <max_teams> <description>"""
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /create <name> <max_teams> <description>")
        return
    
    name = context.args[0]
    try:
        max_teams = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Max teams must be a number!")
        return
    
    description = ' '.join(context.args[2:])
    
    tournament_id = f"tournament_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    tournaments[tournament_id] = {
        'id': tournament_id,
        'name': name,
        'max_teams': max_teams,
        'description': description,
        'status': 'active',
        'created_at': datetime.now().isoformat()
    }
    
    if save_data(tournaments, TOURNAMENTS_FILE):
        await update.message.reply_text(
            f"✅ Tournament created!\n"
            f"Name: {name}\n"
            f"Max teams: {max_teams}\n"
            f"Description: {description}\n\n"
            f"ID: {tournament_id}"
        )
    else:
        await update.message.reply_text("❌ Failed to create tournament!")

async def generate_bracket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate tournament bracket - /generate_bracket <tournament_id>"""
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /generate_bracket <tournament_id>")
        return
    
    tournament_id = context.args[0]
    if tournament_id not in tournaments:
        await update.message.reply_text("❌ Tournament not found!")
        return
    
    tournament_teams = [t for t in teams.values() if t.get('tournament_id') == tournament_id and t.get('status') == 'active']
    
    if len(tournament_teams) < 2:
        await update.message.reply_text("❌ Need at least 2 teams to generate bracket!")
        return
    
    # Simple bracket generation
    random.shuffle(tournament_teams)
    matches = []
    
    for i in range(0, len(tournament_teams), 2):
        if i + 1 < len(tournament_teams):
            match_id = f"match_{tournament_id}_{len(matches)}"
            matches.append({
                'id': match_id,
                'team1': tournament_teams[i],
                'team2': tournament_teams[i + 1],
                'winner': None,
                'round': 1
            })
    
    tournaments[tournament_id]['bracket'] = {
        'matches': matches,
        'current_round': 1,
        'status': 'active'
    }
    tournaments[tournament_id]['status'] = 'started'
    
    if save_data(tournaments, TOURNAMENTS_FILE):
        await update.message.reply_text(f"✅ Bracket generated for {tournaments[tournament_id]['name']}!")
        await send_bracket_to_admins(context, tournament_id)
    else:
        await update.message.reply_text("❌ Failed to generate bracket!")

async def send_bracket_to_admins(context, tournament_id):
    """Send bracket to admins"""
    tournament = tournaments[tournament_id]
    bracket = tournament['bracket']
    
    text = f"🎯 Bracket for {tournament['name']} - Round 1:\n\n"
    
    for match in bracket['matches']:
        team2_name = match['team2']['name'] if match['team2'] else "BYE"
        text += f"⚔️ {match['team1']['name']} vs {team2_name}\n"
        
        if match['team2']:  # Only show buttons if it's a real match
            keyboard = [
                [
                    InlineKeyboardButton(f"🏆 {match['team1']['name']}", 
                                      callback_data=f"report_winner_{match['id']}_{match['team1']['id']}"),
                    InlineKeyboardButton(f"🏆 {team2_name}", 
                                      callback_data=f"report_winner_{match['id']}_{match['team2']['id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            for admin_id in ADMINS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"Match: {match['team1']['name']} vs {team2_name}",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Failed to send match to admin {admin_id}: {e}")
    
    await notify_admins(context, text)

async def report_match_winner(query, context, match_id, winner_team_id):
    """Report match winner"""
    tournament_id = match_id.split('_')[1]
    
    if tournament_id not in tournaments:
        await query.edit_message_text("❌ Tournament not found!")
        return
    
    tournament = tournaments[tournament_id]
    match = next((m for m in tournament['bracket']['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.edit_message_text("❌ Match not found!")
        return
    
    match['winner'] = winner_team_id
    save_data(tournaments, TOURNAMENTS_FILE)
    
    winner_team = teams[winner_team_id]
    await query.edit_message_text(f"✅ Winner recorded: {winner_team['name']}")
    
    # Check if round is complete
    await check_round_completion(context, tournament_id)

async def check_round_completion(context, tournament_id):
    """Check if current round is complete and generate next round"""
    tournament = tournaments[tournament_id]
    current_round = tournament['bracket']['current_round']
    current_matches = [m for m in tournament['bracket']['matches'] if m['round'] == current_round]
    
    if all(m.get('winner') for m in current_matches):
        await generate_next_round(context, tournament_id)

async def generate_next_round(context, tournament_id):
    """Generate next round matches"""
    tournament = tournaments[tournament_id]
    current_round = tournament['bracket']['current_round']
    winners = [m['winner'] for m in tournament['bracket']['matches'] if m['round'] == current_round and m['winner']]
    
    if len(winners) <= 1:
        await finish_tournament(context, tournament_id, winners[0] if winners else None)
        return
    
    # Create next round
    next_round = current_round + 1
    matches = []
    
    for i in range(0, len(winners), 2):
        if i + 1 < len(winners):
            match_id = f"match_{tournament_id}_{len(tournament['bracket']['matches'])}"
            matches.append({
                'id': match_id,
                'team1': teams[winners[i]],
                'team2': teams[winners[i + 1]],
                'winner': None,
                'round': next_round
            })
    
    tournament['bracket']['matches'].extend(matches)
    tournament['bracket']['current_round'] = next_round
    save_data(tournaments, TOURNAMENTS_FILE)
    
    await send_next_round_to_admins(context, tournament_id, next_round)

async def send_next_round_to_admins(context, tournament_id, round_number):
    """Send next round to admins"""
    tournament = tournaments[tournament_id]
    round_matches = [m for m in tournament['bracket']['matches'] if m['round'] == round_number]
    
    text = f"🎯 Round {round_number}:\n\n"
    
    for match in round_matches:
        text += f"⚔️ {match['team1']['name']} vs {match['team2']['name']}\n"
        
        keyboard = [
            [
                InlineKeyboardButton(f"🏆 {match['team1']['name']}", 
                                  callback_data=f"report_winner_{match['id']}_{match['team1']['id']}"),
                InlineKeyboardButton(f"🏆 {match['team2']['name']}", 
                                  callback_data=f"report_winner_{match['id']}_{match['team2']['id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        for admin_id in ADMINS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"Match: {match['team1']['name']} vs {match['team2']['name']}",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Failed to send match to admin {admin_id}: {e}")
    
    await notify_admins(context, text)

async def finish_tournament(context, tournament_id, winner_team_id):
    """Finish tournament and announce results"""
    tournament = tournaments[tournament_id]
    winner_team = teams[winner_team_id] if winner_team_id else None
    
    if winner_team:
        text = (
            f"🏆 TOURNAMENT FINISHED! 🏆\n\n"
            f"Tournament: {tournament['name']}\n"
            f"1st Place: {winner_team['name']} 🥇\n"
            f"Congratulations to the winners! 🎉"
        )
    else:
        text = f"Tournament {tournament['name']} finished!"
    
    await notify_admins(context, text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all messages"""
    if update.message and update.message.text and not update.message.text.startswith('/'):
        user_id = update.effective_user.id
        if user_id in user_states:
            state = user_states[user_id].get('state')
            if state == 'waiting_team_name':
                await handle_team_name(update, context)
            elif state == 'waiting_leader_username':
                await handle_leader_username(update, context)

def main():
    """Start the bot"""
    # Get bot token from environment variable
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("create", create_tournament))
    application.add_handler(CommandHandler("generate_bracket", generate_bracket))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    port = int(os.environ.get('PORT', 8443))
    webhook_url = os.getenv('WEBHOOK_URL')
    
    if webhook_url:
        # Webhook mode for production
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=f"{webhook_url}/{token}"
        )
    else:
        # Polling mode for development
        application.run_polling()

if __name__ == '__main__':
    main()
