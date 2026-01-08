# Login System 
from text_lib import to_reverse

def login_system(user, password):
    if user == 'your_username' and password == 'your_password':
        print('Login successful!')
        print(to_reverse(user)) # Use text_lib's to_reverse function to reverse the username
    else:
        print('Invalid username or password. Please try again.') 
login_system('test_user', 'test_pass')