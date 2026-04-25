# greetingAgent/checkIfUserExist.py
from movieRecommendation.entities.user import User

def checkUserExist(user_name: str):
    """Only used for returning users who already exist."""
    user = User.get_user(user_name=user_name)
    if user:
        User.update_login_timestamp(user['user_id'])
        print(f"Returning existing user: {user['user_name']} (ID: {user['user_id']})")
    return user