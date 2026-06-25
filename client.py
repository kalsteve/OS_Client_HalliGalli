# client.py
import socket
import os
import select
import sys

try:
    from PyQt5.QtGui import QPixmap
    from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, \
        QGridLayout, QFrame, QDialog, QDialogButtonBox, QSizePolicy
    from PyQt5.QtCore import Qt, QThread, pyqtSignal
except ModuleNotFoundError as exc:
    if exc.name == "PyQt5":
        venv_python = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
        if (
            os.path.exists(venv_python)
            and os.path.realpath(sys.executable) != os.path.realpath(venv_python)
            and sys.argv
            and sys.argv[0] not in ("", "-c")
        ):
            os.execv(venv_python, [venv_python, os.path.abspath(sys.argv[0])] + sys.argv[1:])
    raise

from DataConverter import BUFFER_SIZE, DataConverter

buffer_size = BUFFER_SIZE
server_host = os.environ.get("HALLIGALLI_HOST", "127.0.0.1")
server_port = int(os.environ.get("HALLIGALLI_PORT", "4848"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_PLAYER_SLOTS = 6
CARD_SIZE = (108, 146)

APP_STYLE = """
QWidget#lobbyRoot, QWidget#gameRoot {
    background: #12372a;
    color: #f7fbf8;
    font-family: Arial;
}
QLabel#titleLabel {
    color: #f7fbf8;
    font-size: 26px;
    font-weight: 700;
}
QLabel#subtitleLabel, QLabel#statusMessage {
    color: #cfe6d9;
    font-size: 14px;
}
QLabel#turnLabel {
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
}
QFrame#playerPanel {
    background: #184a38;
    border: 1px solid #2d6a4f;
    border-radius: 8px;
}
QFrame#playerPanel[active="true"] {
    border: 3px solid #ffd166;
    background: #1e5b43;
}
QFrame#playerPanel[me="true"] {
    border-color: #74c0fc;
}
QLabel#playerName {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#playerMeta {
    color: #d8f3dc;
    font-size: 12px;
}
QLabel#playerScore {
    color: #ffd166;
    font-size: 13px;
    font-weight: 700;
}
QLabel#playerStatus {
    color: #f7fbf8;
    font-size: 12px;
    font-weight: 700;
}
QLabel#cardImage {
    background: #0b1f18;
    border: 1px solid #315f4b;
    border-radius: 6px;
}
QPushButton {
    min-height: 38px;
    border-radius: 6px;
    border: 1px solid #d8f3dc;
    background: #f7fbf8;
    color: #12372a;
    font-weight: 700;
}
QPushButton:hover:enabled {
    background: #d8f3dc;
}
QPushButton:disabled {
    background: #6c7f75;
    color: #263d33;
    border-color: #6c7f75;
}
QPushButton#bellButton {
    background: #ffd166;
    border-color: #f4a261;
    color: #3d2c00;
}
QPushButton#bellButton:hover:enabled {
    background: #ffe08a;
}
"""

PLAYER_STATUS_TEXT = {
    DataConverter.player_action["PLAYER_INIT"]: "입장",
    DataConverter.player_action["PLAYER_READY"]: "준비",
    DataConverter.player_action["PLAYER_GAMING"]: "진행 중",
    DataConverter.player_action["PLAYER_TURN"]: "차례",
    DataConverter.player_action["PLAYER_LOSE"]: "패배",
    DataConverter.player_action["PLAYER_WIN"]: "승리",
    DataConverter.player_action["PLAYER_NOT_WANT"]: "시작 준비",
}


def asset_path(file_name: str) -> str:
    return os.path.join(BASE_DIR, "images", file_name)


def scaled_pixmap(file_name: str, width: int, height: int) -> QPixmap:
    return QPixmap(asset_path(file_name)).scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def receive_packet(client_socket: socket.socket) -> bytes:
    chunks = []
    received = 0

    while received < buffer_size:
        chunk = client_socket.recv(buffer_size - received)
        if not chunk:
            raise ConnectionError("server closed the connection")

        chunks.append(chunk)
        received += len(chunk)

    return b''.join(chunks)

class HarigariClient(QMainWindow):
    def __init__(self):
        super().__init__()

        self.initMainMenu()
        # 통신 설정
        self.clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.clientSocket.connect((server_host, server_port))
            self.data = self.first_receive(self.clientSocket)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Connection Error",
                f"서버에 연결할 수 없습니다.\n{server_host}:{server_port}\n{exc}"
            )
            raise SystemExit(1)

        # 사용하는 버튼
        self.draw_card_button: QPushButton = None
        self.bell_button: QPushButton = None
        self.turn_end_button: QPushButton = None

        # 턴 라벨
        self.turn_label = QLabel(self)
        self.turn_label.setAlignment(Qt.AlignCenter)
        self.turn_label.setStyleSheet("color: white; font-size: 18px;")
        self.status_message_label: QLabel = None
        self.player_panels: list[QFrame] = []
        self.player_name_labels: list[QLabel] = []
        self.player_count_labels: list[QLabel] = []
        self.player_score_labels: list[QLabel] = []
        self.player_status_labels: list[QLabel] = []
        self.game_thread: InGameThread | None = None
        self.wait_thread: waitThread | None = None
        self.waiting_dialog: WaitingDialog | None = None
        self.has_drawn_this_turn = False
        self.current_turn_id = self.data.player_turn
        self.game_over = False
        self.last_lobby_action_ok = True

    def initMainMenu(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("lobbyRoot")
        self.central_widget.setStyleSheet(APP_STYLE)
        self.setCentralWidget(self.central_widget)

        title_image = QLabel(self)
        title_image.setPixmap(scaled_pixmap("title.png", 520, 260))
        title_image.setAlignment(Qt.AlignCenter)
        title_image.setFixedHeight(280)
        title_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        title_label = QLabel("Halli Galli", self)
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignCenter)

        server_label = QLabel(f"Server {server_host}:{server_port}", self)
        server_label.setObjectName("subtitleLabel")
        server_label.setAlignment(Qt.AlignCenter)

        # 게임 시작 버튼
        self.game_start_button = QPushButton('Game Start', self)
        self.game_start_button.clicked.connect(self.handleStartGame)
        self.game_start_button.setEnabled(False)

        # 레디 버튼
        self.ready_button = QPushButton('Ready', self)
        self.ready_button.clicked.connect(self.showReadyScreen)

        self.solo_button = QPushButton('Solo Play', self)
        self.solo_button.clicked.connect(self.handleSoloStart)

        # 레이아웃 설정
        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(56, 48, 56, 48)
        layout.setSpacing(18)
        layout.addStretch(1)
        layout.addWidget(title_image)
        layout.addWidget(title_label)
        layout.addWidget(server_label)
        layout.addSpacing(16)
        layout.addWidget(self.ready_button)
        layout.addWidget(self.solo_button)
        layout.addWidget(self.game_start_button)
        layout.addStretch(1)

        # 제목과 크기
        self.setWindowTitle('Halli Galli')
        self.setMinimumSize(760, 640)
        self.resize(820, 720)

    def initGameScreen(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("gameRoot")
        self.central_widget.setStyleSheet(APP_STYLE)
        self.setCentralWidget(self.central_widget)

        self.turn_label = QLabel(self)
        self.turn_label.setObjectName("turnLabel")
        self.turn_label.setAlignment(Qt.AlignCenter)

        self.status_message_label = QLabel(self)
        self.status_message_label.setObjectName("statusMessage")
        self.status_message_label.setAlignment(Qt.AlignCenter)

        bell_image_label = QLabel(self)
        bell_image_label.setPixmap(scaled_pixmap("bell.png", 72, 72))
        bell_image_label.setAlignment(Qt.AlignCenter)
        bell_image_label.setFixedSize(88, 88)

        self.bell_button = QPushButton('Ring Bell', self)
        self.bell_button.setObjectName("bellButton")
        self.bell_button.clicked.connect(self.handleBellPress)
        self.bell_button.setEnabled(False)

        self.draw_card_button = QPushButton('Draw Card', self)
        self.draw_card_button.clicked.connect(self.handleDrawCard)
        self.draw_card_button.setEnabled(False)

        self.turn_end_button = QPushButton('Turn End', self)
        self.turn_end_button.clicked.connect(self.handleTurnEnd)
        self.turn_end_button.setEnabled(False)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)
        controls_layout.addWidget(self.bell_button)
        controls_layout.addWidget(self.draw_card_button)
        controls_layout.addWidget(self.turn_end_button)

        board_layout = QGridLayout()
        board_layout.setHorizontalSpacing(14)
        board_layout.setVerticalSpacing(14)

        self.player_panels = []
        self.image_labels = []
        self.player_name_labels = []
        self.player_count_labels = []
        self.player_score_labels = []
        self.player_status_labels = []

        for index in range(MAX_PLAYER_SLOTS):
            panel = QFrame(self)
            panel.setObjectName("playerPanel")
            panel.setProperty("active", False)
            panel.setProperty("me", False)
            panel.setMinimumSize(190, 238)
            panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(12, 10, 12, 10)
            panel_layout.setSpacing(6)

            name_label = QLabel(f"Player {index + 1}", panel)
            name_label.setObjectName("playerName")
            name_label.setAlignment(Qt.AlignCenter)

            image_label = QLabel(panel)
            image_label.setObjectName("cardImage")
            image_label.setPixmap(scaled_pixmap("back.png", *CARD_SIZE))
            image_label.setFixedSize(*CARD_SIZE)
            image_label.setAlignment(Qt.AlignCenter)

            count_label = QLabel("Hand 0 / Table 0", panel)
            count_label.setObjectName("playerMeta")
            count_label.setAlignment(Qt.AlignCenter)

            score_label = QLabel("Score 0", panel)
            score_label.setObjectName("playerScore")
            score_label.setAlignment(Qt.AlignCenter)

            status_label = QLabel("대기", panel)
            status_label.setObjectName("playerStatus")
            status_label.setAlignment(Qt.AlignCenter)

            panel_layout.addWidget(name_label)
            panel_layout.addWidget(image_label, alignment=Qt.AlignCenter)
            panel_layout.addWidget(count_label)
            panel_layout.addWidget(score_label)
            panel_layout.addWidget(status_label)

            row = index // 3
            col = index % 3
            board_layout.addWidget(panel, row, col)

            self.player_panels.append(panel)
            self.image_labels.append(image_label)
            self.player_name_labels.append(name_label)
            self.player_count_labels.append(count_label)
            self.player_score_labels.append(score_label)
            self.player_status_labels.append(status_label)

        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(self.turn_label)
        layout.addWidget(self.status_message_label)
        layout.addWidget(bell_image_label, alignment=Qt.AlignCenter)
        layout.addLayout(board_layout)
        layout.addLayout(controls_layout)

        self.bell_button.setEnabled(True)
        self.receive_data(self.data)
        self.updateTurnControls()

        self.setWindowTitle('Halli Galli')
        self.setMinimumSize(860, 720)
        self.resize(940, 820)
        self.show()

    # 서버에 신호를 보냄
    def first_receive(self, client_socket: socket.socket):
        print("Signal sent to server")
        data = DataConverter(receive_packet(client_socket))
        print("Received data from server: ", data)
        return data

    # 카드를 뽑았을때
    def handleDrawCard(self):
        if self.game_thread is None:
            return

        self.has_drawn_this_turn = True
        self.draw_card_button.setEnabled(False)
        self.turn_end_button.setEnabled(True)
        self.game_thread.update_event(clicked_draw_button=True)
        print("Draw card pressed!")

    # 밸 눌렀을때
    def handleBellPress(self):
        if self.game_thread is not None:
            self.game_thread.update_event(clicked_bell_button=True)
        print("Bell pressed!")

    def handleMyTurn(self):
        self.updateTurnControls()
        print("My turn!")

    def handleNotMyTurn(self):
        self.has_drawn_this_turn = False
        self.updateTurnControls()
        print("Not my turn!")

    def handlePlayerReady(self, action):
        # 'PLAYER_NOT_WANT' 액션 처리
        try:
            self.data.set_action(action)
            self.clientSocket.sendall(bytes(self.data))
            print("set action: ", self.data.get_action())
            self.data.recv(receive_packet(self.clientSocket))
            print("Received action from server:", self.data)
            self.last_lobby_action_ok = True
            return True
        except (ConnectionError, OSError, ValueError) as exc:
            self.last_lobby_action_ok = False
            QMessageBox.warning(self, "Connection Closed", str(exc))
            return False

    def handleSoloStart(self):
        self.ready_button.setEnabled(False)
        self.solo_button.setEnabled(False)

        action = DataConverter.player_action.get("PLAYER_NOT_WANT")
        if not self.handlePlayerReady(action):
            self.ready_button.setEnabled(True)
            self.solo_button.setEnabled(True)
            return

        self.game_start_button.setEnabled(True)
        if not self.handleStartGame():
            self.ready_button.setEnabled(True)
            self.solo_button.setEnabled(True)

    def handleTurnEnd(self):
        if self.game_thread is None:
            return

        self.has_drawn_this_turn = False
        self.turn_end_button.setEnabled(False)
        self.game_thread.update_event(clicked_turn_end_button=True)
        print("Turn end pressed!")

    def handleOffButton(self):
        self.turn_end_button.setEnabled(False)

    def handleGameOver(self, result_message):
        self.game_over = True
        self.has_drawn_this_turn = False
        if self.turn_label is not None:
            self.turn_label.setText("Game Over")
        if self.status_message_label is not None:
            self.status_message_label.setText(result_message)
        self.updateTurnControls()
        QMessageBox.information(self, "Game Over", result_message)

    def handleConnectionClosed(self, message):
        self.game_over = True
        self.updateTurnControls()
        QMessageBox.warning(self, "Connection Closed", message)

    def handleWaitingFinished(self):
        if self.waiting_dialog is not None:
            self.waiting_dialog.close()
            self.waiting_dialog = None

        if self.wait_thread is not None:
            if not self.wait_thread.completed:
                self.wait_thread = None
                QMessageBox.warning(self, "Connection Closed", "게임 시작 대기 중 서버 연결이 종료되었습니다.")
                return

            self.data = self.wait_thread.data
            self.wait_thread = None

        self.game_start_button.setEnabled(True)
        self.showGameScreen()

    def handleStartGame(self):
        try:
            self.clientSocket.sendall(self.data.send("PLAYER_START"))
            print("init send data from server: ", bytes(self.data))
            self.data.recv(receive_packet(self.clientSocket))
            print("init Received action from server:", self.data)
        except (ConnectionError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Connection Closed", str(exc))
            return False

        self.ready_button.setEnabled(False)
        self.solo_button.setEnabled(False)
        self.game_start_button.setEnabled(False)
        self.showGameScreen()
        return True

    # 게임 화면을 보여줌
    def showGameScreen(self):
        self.initGameScreen()
        self.game_thread = InGameThread(parent=self, client_socket=self.clientSocket, data=self.data)
        self.game_thread.cardUpdateSignal.connect(self.receive_data)
        self.game_thread.myTurnSignal.connect(self.handleMyTurn)
        self.game_thread.notMyTurnSignal.connect(self.handleNotMyTurn)
        self.game_thread.offBellButtonSignal.connect(self.handleOffButton)
        self.game_thread.gameOverSignal.connect(self.handleGameOver)
        self.game_thread.connectionClosedSignal.connect(self.handleConnectionClosed)
        self.game_thread.start()

        self.show()

    # 준비 버튼을 누르면 게임 시작 버튼이 활성화됨
    def showReadyScreen(self):
        self.ready_button.setStyleSheet("color: red;")

        # Create a confirmation dialog
        dialog = ReadyConfirmationDialog(self)
        dialog.playerReadySignal.connect(self.handlePlayerReady)
        dialog.PlayerStartSignal.connect(self.handleStartGame)
        result = dialog.exec_()

        if not self.last_lobby_action_ok:
            self.ready_button.setStyleSheet("")
            self.ready_button.setEnabled(True)
            self.solo_button.setEnabled(True)
            return

        if result == QDialog.Rejected:
            # 레디버튼 비활성화, 게임시작버튼 활성화
            self.ready_button.setEnabled(False)
            self.solo_button.setEnabled(False)
            self.game_start_button.setEnabled(True)


        elif result == QDialog.Accepted:
            # 레디버튼 비활성화
            self.ready_button.setEnabled(False)
            self.solo_button.setEnabled(False)

            # 대기중 다이얼로그 생성
            self.waiting_dialog = WaitingDialog(self)
            self.waiting_dialog.show()

            # 대기중 쓰레드 생성
            self.wait_thread = waitThread(parent=self, client_socket=self.clientSocket, data=self.data)
            self.wait_thread.finished.connect(self.handleWaitingFinished)
            self.wait_thread.start()

    def receive_data(self, data: DataConverter):
        self.data = data
        current_player = data.get_turn()
        current_player_index = data.get_turn_index()
        player_list = data.get_player_list()

        if self.current_turn_id != current_player:
            self.current_turn_id = current_player
            self.has_drawn_this_turn = False

        for index, label in enumerate(self.image_labels):
            image_path = asset_path("back.png")
            is_active = False
            is_me = False

            if index < len(player_list):
                card = player_list[index]["card"]
                player = player_list[index]
                player_index = player.get("player_index", index + 1)
                is_me = player.get("player_id") == data.my_id
                is_active = player.get("player_id") == current_player
                name_suffix = " (나)" if is_me else ""
                self.player_name_labels[index].setText(f"Player {player_index}{name_suffix}")
                self.player_count_labels[index].setText(
                    f"Hand {player.get('hand_count', 0)} / Table {player.get('table_count', 0)}"
                )
                self.player_score_labels[index].setText(f"Score {player.get('score', player.get('total_count', 0))}")
                self.player_status_labels[index].setText(
                    PLAYER_STATUS_TEXT.get(player.get("player_status"), "진행 중")
                )

                if card["type"] != "CARD_NULL" and card["volume"] >= 0:
                    card_type = card["type"].lower()
                    card_volume = card["volume"] + 1
                    candidate_path = asset_path(f"{card_type}{card_volume}.jpg")
                    if os.path.exists(candidate_path):
                        image_path = candidate_path
            else:
                self.player_name_labels[index].setText(f"Player {index + 1}")
                self.player_count_labels[index].setText("Hand - / Table -")
                self.player_score_labels[index].setText("Score -")
                self.player_status_labels[index].setText("대기")

            self.player_panels[index].setProperty("active", is_active)
            self.player_panels[index].setProperty("me", is_me)
            self.player_panels[index].style().unpolish(self.player_panels[index])
            self.player_panels[index].style().polish(self.player_panels[index])
            label.setPixmap(QPixmap(image_path).scaled(*CARD_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # 화면 상단에 현재 플레이어 누군지 표시
        if current_player == data.my_id:
            self.turn_label.setText("Current Turn: You")
            self.status_message_label.setText("내 차례입니다.")
        elif current_player_index:
            self.turn_label.setText(f"Current Turn: Player {current_player_index}")
            self.status_message_label.setText(f"Player {current_player_index} 차례입니다.")
        else:
            self.turn_label.setText("Current Turn: -")
            self.status_message_label.setText("게임 상태를 기다리는 중입니다.")

        self.updateTurnControls()

    def updateTurnControls(self):
        if self.draw_card_button is None or self.turn_end_button is None or self.bell_button is None:
            return

        if self.game_over:
            self.draw_card_button.setEnabled(False)
            self.turn_end_button.setEnabled(False)
            self.bell_button.setEnabled(False)
            return

        my_player = self.data.get_my_player()
        my_hand_count = my_player.get("hand_count", 0) if my_player else 0
        is_my_turn = self.data.my_id == self.data.player_turn

        self.draw_card_button.setEnabled(is_my_turn and not self.has_drawn_this_turn and my_hand_count > 0)
        self.turn_end_button.setEnabled(is_my_turn and (self.has_drawn_this_turn or my_hand_count == 0))
        self.bell_button.setEnabled(True)

    # 게임 화면을 닫으면 소켓도 닫힘
    def closeEvent(self, event):
        try:
            self.clientSocket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        if self.wait_thread is not None and self.wait_thread.isRunning():
            self.wait_thread.stop()
            self.wait_thread.wait(1000)

        if self.game_thread is not None and self.game_thread.isRunning():
            self.game_thread.stop()
            self.game_thread.wait(1000)

        self.clientSocket.close()
        event.accept()


# 레디 버튼을 누르면 뜨는 창
class ReadyConfirmationDialog(QDialog):
    playerReadySignal = pyqtSignal(int)
    PlayerStartSignal = pyqtSignal()

    def __init__(self, parent=None):
        super(ReadyConfirmationDialog, self).__init__(parent)
        self.setWindowTitle('Ready Confirmation')
        self.setMinimumWidth(300)

        # 버튼 설정
        self.button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # 레이아웃 설정
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel('다른 플레이어를 기다릴까요?'))
        self.layout.addWidget(self.button_box)

    # 게임 다른 플레이어를 기다림
    def accept(self):
        super(ReadyConfirmationDialog, self).accept()
        action = DataConverter.player_action.get("PLAYER_READY")
        self.playerReadySignal.emit(action)

    # 다른 플레이어를 기다리지 않음
    def reject(self):
        super(ReadyConfirmationDialog, self).reject()
        action = DataConverter.player_action.get("PLAYER_NOT_WANT")
        self.playerReadySignal.emit(action)


class WaitingDialog(QDialog):
    playerWaitingSignal = pyqtSignal(int)

    def __init__(self, parent=None):
        super(WaitingDialog, self).__init__(parent)
        self.setWindowTitle("대기 중")
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        label = QLabel("게임 시작을 기다리는 중입니다...", self)
        layout.addWidget(label)
        self.setLayout(layout)


class InGameThread(QThread):
    cardUpdateSignal = pyqtSignal(DataConverter)
    myTurnSignal = pyqtSignal()
    notMyTurnSignal = pyqtSignal()
    offBellButtonSignal = pyqtSignal()
    gameOverSignal = pyqtSignal(str)
    connectionClosedSignal = pyqtSignal(str)

    def __init__(self, parent=None, client_socket=None, data=None):
        super(InGameThread, self).__init__(parent)
        self.clientSocket: socket.socket = client_socket
        self.data: DataConverter = DataConverter(data)
        self.clicked_draw_button: bool = False
        self.clicked_bell_button: bool = False
        self.clicked_turn_end_button: bool = False
        self.running: bool = True

    def update_event(self, clicked_draw_button=False, clicked_bell_button=False, clicked_turn_end_button=False):
        self.clicked_draw_button = clicked_draw_button
        self.clicked_bell_button = clicked_bell_button
        self.clicked_turn_end_button = clicked_turn_end_button

    def stop(self):
        self.running = False

    def emit_turn_state(self):
        if self.data.my_id == self.data.player_turn:
            self.myTurnSignal.emit()
        else:
            self.notMyTurnSignal.emit()

    def build_game_over_message(self, action: str) -> str:
        my_score = self.data.get_my_score()
        winner_index = self.data.get_winner_index()
        is_solo_game = len(self.data.get_player_list()) == 1

        if action == "PLAYER_WIN":
            if winner_index == self.data.my_index:
                return f"승리했습니다!\n최종 점수: {my_score}"
            return f"Player {winner_index} 승리!\n내 최종 점수: {my_score}"

        if is_solo_game and not winner_index:
            return f"게임 종료!\n최종 점수: {my_score}"

        if winner_index:
            return f"Player {winner_index} 승리. 패배했습니다.\n내 최종 점수: {my_score}"

        return f"게임 종료.\n최종 점수: {my_score}"

    def receive_and_emit(self):
        try:
            self.data.recv(receive_packet(self.clientSocket))
        except (ConnectionError, OSError, ValueError) as exc:
            self.connectionClosedSignal.emit(str(exc))
            self.running = False
            return False

        print("Received action from server:", self.data)

        if self.data.stored_dict.get("all_players_data") is not None:
            self.cardUpdateSignal.emit(self.data)
        else:
            action = self.data.get_action()
            if action == "PLAYER_WIN":
                self.gameOverSignal.emit(self.build_game_over_message(action))
                self.running = False
                return False
            if action == "PLAYER_LOSE":
                self.gameOverSignal.emit(self.build_game_over_message(action))
                self.running = False
                return False
            self.emit_turn_state()

        return True

    def send_action(self, action):
        try:
            self.clientSocket.sendall(bytes(self.data.send(action)))
            print("send data from server: ", bytes(self.data))
            return True
        except OSError as exc:
            self.connectionClosedSignal.emit(str(exc))
            self.running = False
            return False

    def receive_if_available(self):
        readable, _, _ = select.select([self.clientSocket], [], [], 0.05)
        if readable:
            return self.receive_and_emit()
        return True

    def run(self):
        self.emit_turn_state()
        while self.running:
            if self.clicked_bell_button:
                self.clicked_bell_button = False
                if not self.send_action("PLAYER_BELL"):
                    break
                if not self.receive_and_emit():
                    break
                self.offBellButtonSignal.emit()


            # 플레이어의 턴인 상태면
            if self.data.my_id == self.data.player_turn:
                # 데이터의 업데이트를 대기
                if self.clicked_draw_button:
                    self.clicked_draw_button = False
                    if not self.send_action("PLAYER_DRAW"):
                        break
                    if not self.receive_and_emit():
                        break

                if self.clicked_turn_end_button:
                    self.clicked_turn_end_button = False
                    if not self.send_action("PLAYER_TURN_END"):
                        break
                    if not self.receive_and_emit():
                        break

            self.clicked_draw_button = False
            self.clicked_turn_end_button = False
            if not self.receive_if_available():
                break
            QThread.msleep(50)

class waitThread(QThread):
    def __init__(self, parent=None, client_socket=None, data=None):
        super(waitThread, self).__init__(parent)
        self.clientSocket: socket.socket = client_socket
        self.data: DataConverter = DataConverter(data)
        self.running = True
        self.completed = False

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                self.data.recv(receive_packet(self.clientSocket))
            except (ConnectionError, OSError, ValueError):
                break
            print("Received action from server:", self.data)
            if self.data.my_action != self.data.player_action["PLAYER_READY"]:
                self.completed = True
                break

if __name__ == '__main__':
    app = QApplication([])
    client = HarigariClient()
    client.show()
    app.exec_()
