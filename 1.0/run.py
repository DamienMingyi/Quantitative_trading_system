# flake8: noqa
from engine import EventEngine

from MainEngine import MainEngine
from init import create_qapp
from mainwindow import MainWindow


from choros import ChronosGateway




def main():
    """"""
    qapp = create_qapp()

    event_engine = EventEngine()

    main_engine = MainEngine(event_engine)

    main_engine.add_gateway(ChronosGateway)

    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()

    qapp.exec()


if __name__ == "__main__":
    main()
