from flask import Flask

from app.routes import *

if __name__ == '__main__':
    app.run(debug=False)