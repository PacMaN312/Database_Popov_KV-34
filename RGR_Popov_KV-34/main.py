# main.py
from controllers import Controller

def main():
    ctrl = Controller()
    try:
        ctrl.run()
    finally:
        ctrl.close()

if __name__ == "__main__":
    main()
