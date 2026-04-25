"""User entity module"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, ConfigDict
from config import load_config
import psycopg2
from datetime import date
import json

class MoviePreferences(BaseModel):
    """Represents a user's movie preferences."""
    movie_interests_titles: List[str]
    liked_genres: List[str]
    excluded_genres: List[str]
    min_rating: Optional[float]  # Default minimum rating
    extra_prefs: Dict[str, Any] = {}
    model_config = ConfigDict(from_attributes=True)

class User(BaseModel):
    """Represents a user."""
    user_id: Optional[int] = None
    user_name: str
    user_start_date: str
    last_logged_in_date: str
    years_as_user: int
    preferences: MoviePreferences
    model_config = ConfigDict(from_attributes=True)

    def to_json(self) -> str:
        """Convert the User object to JSON string.
        Returns:
            a JSON string representing the User object."""
        return self.model_dump_json(indent=4)

    @staticmethod 
    def get_user(current_user_id: Optional[int] = None, user_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves a user by ID or by username (case-insensitive).
        Prioritizes user_id if both are provided.
        Args:
            current_user_id: The ID of the user to retrieve.
            user_name: The username to search for (case-insensitive).
        Returns:
            The User dictionary if found, None otherwise."""
        config = load_config()
        try:
            with psycopg2.connect(**config) as conn:
                with conn.cursor() as cur:
                    if current_user_id is not None:
                        cur.execute("select user_id, user_name, user_start_date, last_logged_in_date, years_as_user, preferences from users where user_id = %s", (current_user_id,))
                    elif user_name is not None:
                        cur.execute("select user_id, user_name, user_start_date, last_logged_in_date, years_as_user, preferences from users where LOWER(user_name) = LOWER(%s)", (user_name.strip(),))
                    else:
                        print("No user_id or user_name provided.")
                        return None
                    rows = cur.fetchall()
                    if rows:
                        for row in rows:
                            user = User(
                                user_id=row[0],
                                user_name=row[1],
                                user_start_date=str(row[2]),
                                last_logged_in_date=str(row[3]), 
                                years_as_user=row[4],
                                preferences=MoviePreferences.model_validate(row[5])
                            )
                            print(f"User found: {user.user_name}")
                            # Adhere to ADK: return only the serializable dictionary
                            return user.model_dump()
                    elif len(rows) == 0:
                        print(f"No user found for {'ID ' + str(current_user_id) if current_user_id is not None else 'name ' + user_name}")
                        return None
        except (psycopg2.DatabaseError, Exception) as error:
            print(f"Error: {error}")

    @staticmethod
    def create_user(user_name: Optional[str] = None, liked_genres: Optional[list]=None) -> Dict[str, Any]:
        """Generates the initial preferences for a brand new visitor.
        Returns:
            A dictionary representing the new user."""
        print(f"Creating a new user profile...")
        today = date.today().isoformat()
        new_user = {
            "user_name": user_name,
            "user_start_date": today,
            "last_logged_in_date": today,
            "years_as_user": 0,
            "preferences": {
                "movie_interests_titles": [],
                "liked_genres": liked_genres,
                "excluded_genres": [],
                "min_rating": 5.0,
                "extra_prefs": {}
            }
        }
        return new_user
    
    @staticmethod
    def save_userData_to_db(user_data: Dict[str, Any]) -> Optional[int]:
        """STRICTLY FOR NEW USERS.
        Inserts a new record and returns the database-generated ID."""
        config = load_config()
        try:
            with psycopg2.connect(**config) as conn:
                with conn.cursor() as cur:
                    prefs_json = json.dumps(user_data["preferences"])
                    cur.execute("insert into users (user_name, user_start_date, last_logged_in_date, years_as_user, preferences) values (%s, %s, %s, %s, %s) returning user_id",
                                (user_data["user_name"], user_data["user_start_date"], user_data["last_logged_in_date"], user_data["years_as_user"], prefs_json))
                    generated_id = cur.fetchone()[0]
                    conn.commit()
                    print(f"New user data saved with ID: {generated_id} for {user_data['user_name']}.")
                    return generated_id
        except (psycopg2.DatabaseError, Exception) as error:
            print(f"Error: {error}")

    @staticmethod
    def update_login_timestamp(current_user_id: int) -> None:
        """Updates the last logged in date for the user."""
        config = load_config()
        today = date.today().isoformat()
        try:
            with psycopg2.connect(**config) as conn:
                with conn.cursor() as cur:
                    cur.execute("update Users Set last_logged_in_date = %s where user_id = %s", (today,current_user_id,))
                    conn.commit()
                    print(f"Current User: {current_user_id}, last login date updated to {today}.")
        except (psycopg2.DatabaseError, Exception) as error:
            print(f"Error: {error}")

    @staticmethod
    def merge_unique(existing_list: List[str], new_items: List[str]) -> List[str]:
        """Helper to merge lists without case-insensitive duplicates."""
        # Create a set of lowercase items already present for fast lookup
        existing_lower = {item.lower() for item in existing_list}
    
        merged = list(existing_list)
        for item in new_items:
            if item.lower() not in existing_lower:
                merged.append(item)
                existing_lower.add(item.lower())
        return merged

    @staticmethod
    def addNewPref(current_user_id: int, incoming_prefs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetches existing preferences, merges new ones accumulatively, and saves to DB.
        - List fields: merged uniquely (case-insensitive)
        - min_rating: updated if provided
        - extra_prefs: deep merge — existing keys are preserved and extended (especially lists)
        - Any unknown top-level key is moved into extra_prefs
        Returns updated preferences dict on success, None on failure."""   
        config = load_config()
        try:
            with psycopg2.connect(**config) as conn:
                with conn.cursor() as cur:
                    # 1. FETCH existing preferences
                    cur.execute("SELECT preferences FROM Users WHERE user_id = %s", (current_user_id,))
                    row = cur.fetchone()
                    if not row:
                        print("User not found.")
                        return None               
                    current_prefs = row[0].copy()  # Work on a copy
                    # Ensure base structure exists
                    list_keys = ["movie_interests_titles", "liked_genres", "excluded_genres"]
                    for key in list_keys:
                        if current_prefs.get(key) is None:
                            current_prefs[key] = []
                    if "min_rating" not in current_prefs:
                        current_prefs["min_rating"] = 5.0
                    if "extra_prefs" not in current_prefs or current_prefs["extra_prefs"] is None:
                        current_prefs["extra_prefs"] = {}
                    # 2. MERGE known list fields (case-insensitive unique append)
                    for key in list_keys:
                        if key in incoming_prefs and isinstance(incoming_prefs[key], list):
                            current_prefs[key] = User.merge_unique(
                                current_prefs.get(key, []), incoming_prefs[key]
                            )
                    # 3. UPDATE min_rating if provided
                    if "min_rating" in incoming_prefs and isinstance(incoming_prefs["min_rating"], (int, float)):
                        current_prefs["min_rating"] = incoming_prefs["min_rating"]
                    # 4. HANDLE extra_prefs: accumulative merge (never overwrite)
                    if "extra_prefs" in incoming_prefs and isinstance(incoming_prefs["extra_prefs"], dict):
                        for key, value in incoming_prefs["extra_prefs"].items():
                            if key not in current_prefs["extra_prefs"]:
                                # New key → just assign
                                current_prefs["extra_prefs"][key] = value
                            else:
                                existing = current_prefs["extra_prefs"][key]
                                if isinstance(existing, list) and isinstance(value, list):
                                    # Both lists → merge uniquely
                                    current_prefs["extra_prefs"][key] = list(set(existing + value))
                                elif isinstance(existing, list):
                                    # Existing is list → append value if not present
                                    if value not in existing:
                                        current_prefs["extra_prefs"][key] = existing + [value]
                                elif isinstance(value, list):
                                    # Incoming is list → prepend existing value
                                    if existing not in value:
                                        current_prefs["extra_prefs"][key] = [existing] + value
                                    else:
                                        current_prefs["extra_prefs"][key] = value
                                else:
                                    # Both scalars → convert to list to accumulate
                                    current_prefs["extra_prefs"][key] = [existing, value]                # 5. MOVE any unknown top-level keys into extra_prefs
                    known_keys = list_keys + ["min_rating", "extra_prefs"]
                    for key, value in list(incoming_prefs.items()):
                        if key not in known_keys:
                            # Accumulate into extra_prefs same way as above
                            if key not in current_prefs["extra_prefs"]:
                                current_prefs["extra_prefs"][key] = value
                            else:
                                existing = current_prefs["extra_prefs"][key]
                                if isinstance(existing, list) and isinstance(value, list):
                                    current_prefs["extra_prefs"][key] = list(set(existing + value))
                                elif isinstance(existing, list):
                                    if value not in existing:
                                        current_prefs["extra_prefs"][key].append(value)
                                elif isinstance(value, list):
                                    if existing not in value:
                                        current_prefs["extra_prefs"][key] = [existing] + value
                                else:
                                    current_prefs["extra_prefs"][key] = [existing, value]
                    # 6. SAVE back to database
                    cur.execute(
                        "UPDATE Users SET preferences = %s WHERE user_id = %s",
                        (json.dumps(current_prefs), current_user_id)
                    )
                    conn.commit()
                    print(f"Successfully updated preferences for user {current_user_id}")
                    return current_prefs
        except (psycopg2.DatabaseError, Exception) as error:
            print(f"Error in addNewPref: {error}")
            if 'conn' in locals():
                conn.rollback()
            return None
        
    @staticmethod
    def deletePref(current_user_id: int, prefs_to_delete: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Remove preferences the user no longer likes.
        Supports:
        - Removing items from known lists (case-insensitive)
        - Removing values from or entire keys in extra_prefs
        - Top-level unknown keys (e.g. {'language': 'english'}) → treated as extra_prefs['language']
        - value=None → delete entire key
        Returns updated preferences on success, None on failure."""    
        config = load_config()
        try:
            with psycopg2.connect(**config) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT preferences FROM users WHERE user_id = %s", (current_user_id,))
                    row = cur.fetchone()
                    if not row:
                        print("User not found.")
                        return None
                    current_prefs = row[0].copy()
                    # Ensure base structure
                    list_keys = ["movie_interests_titles", "liked_genres", "excluded_genres"]
                    for key in list_keys:
                        current_prefs.setdefault(key, [])
                    current_prefs.setdefault("extra_prefs", {})
                    # 1. Remove from known list fields (case-insensitive)
                    for key in list_keys:
                        if key in prefs_to_delete and isinstance(prefs_to_delete[key], list):
                            items_to_remove = {item.strip().lower() for item in prefs_to_delete[key] if item}
                            if not items_to_remove:
                                continue
                            original_len = len(current_prefs[key])
                            current_prefs[key] = [
                                item for item in current_prefs[key]
                                if item.strip().lower() not in items_to_remove
                           ]
                            removed = original_len - len(current_prefs[key])
                            if removed:
                                print(f"Removed {removed} item(s) from {key}")
                    # Helper: remove value from extra_prefs[key] or delete key
                    def remove_from_extra(key: str, value: Any):
                        if key not in current_prefs["extra_prefs"]:
                            print(f"Key '{key}' not found in extra_prefs — nothing to delete")
                            return False
                        current_val = current_prefs["extra_prefs"][key]
                        if value is None:
                            del current_prefs["extra_prefs"][key]
                            print(f"Removed extra_prefs['{key}'] entirely")
                            return True
                        if isinstance(current_val, list):
                            # Case-insensitive for strings
                            if isinstance(value, str):
                                norm_value = value.strip().lower()
                                filtered = [
                                    item for item in current_val
                                    if not (isinstance(item, str) and item.strip().lower() == norm_value)
                                ]
                            else:
                                filtered = [item for item in current_val if item != value]
                            removed_count = len(current_val) - len(filtered)
                            current_prefs["extra_prefs"][key] = filtered  # Moved assignment here
                            if removed_count:
                                print(f"Removed {removed_count} occurrence(s) of '{value}' from extra_prefs['{key}']")
                            if not filtered:
                                del current_prefs["extra_prefs"][key]
                                print(f"Emptied list — removed extra_prefs['{key}']")
                            return removed_count > 0
                        else:
                            # Scalar comparison (case-insensitive if both strings)
                            if isinstance(current_val, str) and isinstance(value, str):
                                if current_val.strip().lower() == value.strip().lower():
                                    del current_prefs["extra_prefs"][key]
                                    print(f"Removed extra_prefs['{key}'] (matched '{value}')")
                                    return True
                            elif current_val == value:
                                del current_prefs["extra_prefs"][key]
                                print(f"Removed extra_prefs['{key}']")
                                return True
                        return False
                    # 2. Handle explicit {'extra_prefs': {...}}
                    if "extra_prefs" in prefs_to_delete and isinstance(prefs_to_delete["extra_prefs"], dict):
                        for k, v in prefs_to_delete["extra_prefs"].items():
                            remove_from_extra(k, v)
                    # 3. Handle top-level unknown keys → route to extra_prefs
                    known_keys = list_keys + ["extra_prefs", "min_rating"]
                    for k, v in prefs_to_delete.items():
                        if k not in known_keys:
                            remove_from_extra(k, v)
                    # Save
                    cur.execute(
                        "UPDATE users SET preferences = %s WHERE user_id = %s",
                        (json.dumps(current_prefs), current_user_id)
                    )
                    conn.commit()
                    print(f"Successfully deleted preferences for user {current_user_id}")
                    return current_prefs
        except (psycopg2.DatabaseError, Exception) as error:
            print(f"Error in deletePref: {error}")
            if 'conn' in locals():
                conn.rollback()
            return None

    @staticmethod
    def delete_inactive_users() -> int:
        """
        Deletes users who haven't logged in for more than 7 days.
        Returns: The number of users deleted.
        """
        config = load_config()
        # PostgreSQL syntax for 1 week
        query = """
            DELETE FROM users 
            WHERE last_logged_in_date < CURRENT_DATE - INTERVAL '7 days'
        """
        try:
            with psycopg2.connect(**config) as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    deleted_count = cur.rowcount
                    conn.commit()
                    print(f"Cleanup finished. {deleted_count} inactive users removed.")
                    return deleted_count
        except (psycopg2.DatabaseError, Exception) as error:
            print(f"Error during cleanup: {error}")
            return 0

          
#if __name__ == '__main__':
    #example usage
    #example = User.get_user(4427162066)
    #if example:
    #    example['preferences']['extra_prefs']['language'] = ['English', 'Spanish']
    #    print(example['preferences']['extra_prefs'])
    #    print(example['user_name'])



    