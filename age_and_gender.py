
import os
import math
import time
import cv2 as cv
import numpy as np
import SSRNET_modee
from SSRNET_modee import SSR_net_general,SSR_net
from google.colab.patches import cv2_imshow

from time import sleep
width = 480
height = 340
face_detector_kind = 'haar'
diagonal, line_thickness = None, None
np.random.seed(int(time.time()))
gender_net = None
age_net = None


# Initialize face detector
if (face_detector_kind == 'haar'):
    face_cascade = cv.CascadeClassifier('haarcascade_frontalface_alt.xml')
else:
    face_net = cv.dnn.readNetFromTensorflow('opencv_face_detector_uint8.pb', 'opencv_face_detector.pbtxt')

# Load age and gender models
if (age_gender_kind == 'ssrnet'):
    face_size = 64
    face_padding_ratio = 0.10
    # Default parameters for SSR-Net
    stage_num = [3, 3, 3]
    lambda_local = 1
    lambda_d = 1
    # Initialize gender net
    gender_net = SSR_net_general(face_size, stage_num, lambda_local, lambda_d)()
    gender_net.load_weights('ssrnet_gender_3_3_3_64_1.0_1.0.h5')
    # Initialize age net
    age_net = SSR_net(face_size, stage_num, lambda_local, lambda_d)()
    age_net.load_weights('ssrnet_age_3_3_3_64_1.0_1.0.h5')



def calculateParameters(height_orig, width_orig):
    global width, height, diagonal, line_thickness
    area = width * height
    width = int(math.sqrt(area * width_orig / height_orig))
    height = int(math.sqrt(area * height_orig / width_orig))
    diagonal = math.sqrt(height * height + width * width)
    # Calculate line thickness to draw boxes
    line_thickness = max(1, int(diagonal / 150))
    # Initialize output video writer
    #sdfs
    
def findFaces(img, confidence_threshold=0.7):
    # Get original width and height
    height = img.shape[0]
    width = img.shape[1]
    
    face_boxes = []

    if (face_detector_kind == 'haar'):
        # Get grayscale image
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        # Detect faces
        detections = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        
        for (x, y, w, h) in detections:
            padding_h = int(math.floor(0.5 + h * face_padding_ratio))
            padding_w = int(math.floor(0.5 + w * face_padding_ratio))
            x1, y1 = max(0, x - padding_w), max(0, y - padding_h)
            x2, y2 = min(x + w + padding_w, width - 1), min(y + h + padding_h, height - 1)
            face_boxes.append([x1, y1, x2, y2])
    else:
        blob = cv.dnn.blobFromImage(img, 1.0, (300, 300), mean=(104, 117, 123), swapRB=True, crop=False)
        face_net.setInput(blob)
        detections = face_net.forward()
        
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if (confidence < confidence_threshold):
                continue
            x1 = int(detections[0, 0, i, 3] * width)
            y1 = int(detections[0, 0, i, 4] * height)
            x2 = int(detections[0, 0, i, 5] * width)
            y2 = int(detections[0, 0, i, 6] * height)
            padding_h = int(math.floor(0.5 + (y2 - y1) * face_padding_ratio))
            padding_w = int(math.floor(0.5 + (x2 - x1) * face_padding_ratio))
            x1, y1 = max(0, x1 - padding_w), max(0, y1 - padding_h)
            x2, y2 = min(x2 + padding_w, width - 1), min(y2 + padding_h, height - 1)
            face_boxes.append([x1, y1, x2, y2])

    return face_boxes


def collectFaces(frame, face_boxes):
    faces = []
    height_orig, width_orig = frame.shape[0:2]
    for i, box in enumerate(face_boxes):
        box_orig = [
            int(round(box[0] * width_orig / width)),
            int(round(box[1] * height_orig / height)),
            int(round(box[2] * width_orig / width)),
            int(round(box[3] * height_orig / height)),
        ]
        face_bgr = frame[
            max(0, box_orig[1]):min(box_orig[3] + 1, height_orig - 1),
            max(0, box_orig[0]):min(box_orig[2] + 1, width_orig - 1),
            :
        ]
        faces.append(face_bgr)
    return faces


def predictAgeGender(faces):
    if (age_gender_kind == 'ssrnet'):
        blob = np.empty((len(faces), face_size, face_size, 3))
        for i, face_bgr in enumerate(faces):
            blob[i, :, :, :] = cv.resize(face_bgr, (64, 64))
            blob[i, :, :, :] = cv.normalize(blob[i, :, :, :], None, alpha=0, beta=255, norm_type=cv.NORM_MINMAX)
        genders = gender_net.predict(blob)
        ages = age_net.predict(blob)
        labels = ['{},{}'.format('Male' if (gender >= 0.5) else 'Female', int(age)) for (gender, age) in zip(genders, ages)]
    
    return labels

# Process video
paused = False
def find_age_gender(frame):
    

    # Calculate parameters if not yet
    if (diagonal is None):
        height_orig, width_orig = frame.shape[0:2]
        calculateParameters(height_orig, width_orig)
        
    # Resize, Convert BGR to HSV
    if ((height, width) != frame.shape[0:2]):
        frame_bgr = cv.resize(frame, dsize=(width, height), fx=0, fy=0)
    else:
        frame_bgr = frame
        
    # Detect faces
    face_boxes = findFaces(frame_bgr)

    # Make a copy of original image
    faces_bgr = frame_bgr.copy()

    if (len(face_boxes) > 0):
        # Draw boxes in faces_bgr image
        for (x1, y1, x2, y2) in face_boxes:
            cv.rectangle(faces_bgr, (x1, y1), (x2, y2), color=(0, 255, 0), thickness=line_thickness, lineType=8)
        
        # Collect all faces into matrix
        faces = collectFaces(frame, face_boxes)
    
        # Get age and gender
        labels = predictAgeGender(faces)
        
        # Draw labels
        for (label, box) in zip(labels, face_boxes):
            cv.putText(faces_bgr, label, org=(box[0], box[1] - 10), fontFace=cv.FONT_HERSHEY_PLAIN,
                       fontScale=1, color=(0, 64, 255), thickness=1, lineType=cv.LINE_AA)

    # Show frames
   # cv.imshow('Source', frame_bgr)
    cv2_imshow(faces_bgr)
    
    # Write output frame
    
cv.destroyAllWindows()



