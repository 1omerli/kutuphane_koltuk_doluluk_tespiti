import cv2
import numpy as np
import matplotlib.pyplot as plt
from ultralytics import YOLO
import threading
from flask import Flask, jsonify, Response, render_template,stream_with_context,request
import requests
import time
from datetime import datetime, timedelta
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

paylasilacak_veri = {"toplam": 0, "dolu": 0, "bos": 0}
alarm_suresi = None
son_gonderilen_veri = None

@app.route('/')
def index():
    return render_template("index.html")  # varsa HTML dosyan

@app.route('/veri', methods=['GET'])
def veri_endpoint():
    return jsonify(paylasilacak_veri)

@app.route('/set_alarm', methods=['POST'])
def set_alarm():
    global alarm_suresi
    data = request.get_json()
    alarm_time = data.get("alarm_time")
    try:
        now = datetime.now()
        alarm_dt = datetime.strptime(alarm_time, "%H:%M")
        alarm_dt = now.replace(hour=alarm_dt.hour, minute=alarm_dt.minute, second=0, microsecond=0)
        if alarm_dt < now:
            alarm_dt += timedelta(days=1)
        alarm_suresi = alarm_dt
        return jsonify({"durum": "Alarm kuruldu", "alarm_saati": alarm_dt.strftime("%H:%M:%S")})
    except Exception as e:
        return jsonify({"hata": str(e)}), 400


@app.route('/alarm-bildirimi', methods=['GET'])
def alarm_bildirimi():
    global alarm_suresi, son_gonderilen_veri
    if alarm_suresi and datetime.now() >= alarm_suresi:
        alarm_suresi = None
        son_gonderilen_veri = paylasilacak_veri.copy()
        return jsonify({"bildirim": "Alarm saati geldi!", "veri": son_gonderilen_veri})
    return jsonify({"bildirim": "Alarm henüz gelmedi."})

# Global olarak tanımla
current_frame = None

def mjpeg_stream():
    global current_frame
    while True:
        if current_frame is None:
            continue
        ret, jpeg = cv2.imencode('.jpg', current_frame)
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(mjpeg_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


def flask_thread():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=flask_thread, daemon=True).start()

# YOLO setup
model = YOLO("yolov8n.pt")
DROIDCAM_URL = "http://192.168.1.200:4747/video"
cap = cv2.VideoCapture(DROIDCAM_URL)

if not cap.isOpened():
    print("🚨 Hata: DroidCam bağlantısı kurulamadı!")
    exit()

results = None

def calculate_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    iou = interArea / float(boxAArea + boxBArea - interArea)
    return iou

def donut_goster():
    plt.ion()
    fig, ax = plt.subplots()
    while True:
        dolu = paylasilacak_veri["dolu"]
        bos = paylasilacak_veri["bos"]
        toplam = dolu + bos

        ax.clear()
        if toplam == 0:
            ax.text(0.5, 0.5, "Sandalye verisi yok", horizontalalignment='center', verticalalignment='center', fontsize=12)
        else:
            labels = ['Dolu', 'Boş']
            sizes = [dolu, bos]
            colors = ['#ff9999', '#66b3ff']
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors,
                                              autopct='%1.1f%%', startangle=140, pctdistance=0.85)
            centre_circle = plt.Circle((0, 0), 0.70, fc='white')
            ax.add_artist(centre_circle)
            ax.axis('equal')

        plt.draw()
        plt.pause(2)

threading.Thread(target=donut_goster, daemon=True).start()

# Ana video işleme döngüsü
while True:
    ret, frame = cap.read()
    if not ret:
        print("🚨 Hata: Görüntü alınamadı!")
        break
    current_frame=frame.copy()
    results = model(frame)
    sandalye_sayisi = 0
    dolu_sandalye = 0
    sandalye_koordinatlari = []
    insan_koordinatlari = []

    for result in results:
        for box in result.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            if cls == 56 and conf > 0.3:
                sandalye_koordinatlari.append((x1, y1, x2, y2))
                sandalye_sayisi += 1
            elif cls == 0 and conf > 0.5:
                insan_koordinatlari.append((x1, y1, x2, y2))

    for sandalye in sandalye_koordinatlari:
        sx1, sy1, sx2, sy2 = sandalye
        dolu_mu = any(
            calculate_iou((sx1, sy1, sx2, sy2), insan) > 0.3
            for insan in insan_koordinatlari
        )

        if dolu_mu:
            dolu_sandalye += 1
            cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), (0, 255, 0), 2)
        else:
            cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), (255, 255, 0), 2)

    bos_sandalye = sandalye_sayisi - dolu_sandalye
    paylasilacak_veri.update({"toplam": sandalye_sayisi, "dolu": dolu_sandalye, "bos": bos_sandalye})

    cv2.putText(frame, f"Toplam Sandalye: {sandalye_sayisi}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, f"Dolu: {dolu_sandalye}", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(frame, f"Bos: {bos_sandalye}", (50, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    cv2.imshow("YOLO - Sandalye ve Insan Tespiti", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()