"""Testing User classes""" #ONLY TO TEST THE CLASSES

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, ConfigDict
from movieRec.createVectorDB.src.config_conn import load_config
import psycopg2
from datetime import date
import json

class MoviePreferences(BaseModel):
    """Represents a user's movie preferences."""
    movie_interests_titles: List[str] # List of movie titles the user has shown interest in
    liked_genres: List[str]
    excluded_genres: List[str]
    model_config = ConfigDict(from_attributes=True)
    
    #convert Movie Preferences object to JSON string
    def to_json(self) -> str:
        """Convert the MoviePreferences object to JSON string.
        Returns:
            a JSON string representing the MoviePreferences object."""
        return self.model_dump_json(indent=4)

class User(BaseModel):
    """Represents a user."""
    user_id: Optional[int] = None
    user_name: str
    preferences: MoviePreferences
    model_config = ConfigDict(from_attributes=True)

    def to_json(self) -> str:
        """Convert the User object to JSON string.
        Returns:
            a JSON string representing the User object."""
        return self.model_dump_json(indent=4)

if __name__ == "__main__":
    #Example usage
    user1 = User(
        user_id=1,
        user_name='Alice',
        preferences=MoviePreferences(
            movie_interests_titles=['Inception', 'The Matrix'],
            liked_genres=['Sci-Fi', 'Action'],
            excluded_genres=['Romance']
        )
    )
    #print(user1.preferences.to_json())
    #print(user1.to_json())
    #print(user1.model_dump())
    #print(user1.model_dump_json(indent=4)) #testing out the func inside to_json
    #print(user1.model_dump_json(indent=4, exclude_none=True))
    #print(user1.model_dump_json(indent=4, exclude={'user_id'}))
    #print(user1.user_name)
