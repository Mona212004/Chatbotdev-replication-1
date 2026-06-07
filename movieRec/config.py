#import python module for reading .ini file
from configparser import ConfigParser
import os

def load_config(filename='db_params.ini', section='postgresql'): 
    parser = ConfigParser() 
    parser.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename))

    # create empty python dict to store connection params
    config = {}
    #check if parser can find section [postgresql]
    if parser.has_section(section):
        params = parser.items(section) #if exist, retrieve all key-value pairs from that section
        for param in params: #loop each pair which are returned as tuples, store in config dict
            config[param[0]] = param[1] #example: {'host': 'localhost'}
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return config

#This block only runs when the Python file is executed directly (not when it's imported as a module). It's used here to test the function.
if __name__ == '__main__':
    config = load_config()
    print(config)
    #{'host': 'localhost', 'database': 'imdb', 'user': 'postgres', 'password': 'postgresPw'}
    
