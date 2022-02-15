# USAGE
# python3 detect_mask_webcam.py

# import the necessary packages
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import img_to_array
from tensorflow.keras.models import load_model
from imutils.video import VideoStream
from flask import Flask, render_template, Response, request
import numpy as np
import argparse
import imutils
import time
import cv2
import os
import rainbowhat

save_img = None
isAlarmActive = True
isViedoFeedActive = True

def detect_and_predict_mask(frame, faceNet, maskNet, args):
	# grab the dimensions of the frame and then construct a blob
	# from it
	(h, w) = frame.shape[:2]
	blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
		(104.0, 177.0, 123.0))

	# pass the blob through the network and obtain the face detections
	faceNet.setInput(blob)
	detections = faceNet.forward()

	# initialize our list of faces, their corresponding locations,
	# and the list of predictions from our face mask network
	faces = []
	locs = []
	preds = []

	# loop over the detections
	for i in range(0, detections.shape[2]):
		# extract the confidence (i.e., probability) associated with
		# the detection
		confidence = detections[0, 0, i, 2]

		# filter out weak detections by ensuring the confidence is
		# greater than the minimum confidence
		if confidence > args["confidence"]:
			# compute the (x, y)-coordinates of the bounding box for
			# the object
			box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
			(startX, startY, endX, endY) = box.astype("int")

			# ensure the bounding boxes fall within the dimensions of
			# the frame
			(startX, startY) = (max(0, startX), max(0, startY))
			(endX, endY) = (min(w - 1, endX), min(h - 1, endY))

			# extract the face ROI, convert it from BGR to RGB channel
			# ordering, resize it to 224x224, and preprocess it
			face = frame[startY:endY, startX:endX]
			face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
			face = cv2.resize(face, (224, 224))
			face = img_to_array(face)
			face = preprocess_input(face)

			# add the face and bounding boxes to their respective
			# lists
			faces.append(face)
			locs.append((startX, startY, endX, endY))

	# only make a predictions if at least one face was detected
	if len(faces) > 0:
		# for faster inference we'll make batch predictions on *all*
		# faces at the same time rather than one-by-one predictions
		# in the above `for` loop
		faces = np.array(faces, dtype="float32")
		preds = maskNet.predict(faces, batch_size=32)

	# return a 2-tuple of the face locations and their corresponding
	# locations
	return (locs, preds)
    
ap = argparse.ArgumentParser()
ap.add_argument("-f", "--face", type=str,
    default="face_detector",
    help="path to face detector model directory")
ap.add_argument("-m", "--model", type=str,
    default="mask_detector.model",
    help="path to trained face mask detector model")
ap.add_argument("-c", "--confidence", type=float, default=0.5,
    help="minimum probability to filter weak detections")
args = vars(ap.parse_args())

# load our serialized face detector model from disk
print("[INFO] loading face detector model...")
prototxtPath = os.path.sep.join([args["face"], "deploy.prototxt"])
weightsPath = os.path.sep.join([args["face"],
    "res10_300x300_ssd_iter_140000.caffemodel"])
faceNet = cv2.dnn.readNet(prototxtPath, weightsPath)

# load the face mask detector model from disk
print("[INFO] loading face mask detector model...")
maskNet = load_model(args["model"])

# initialize the video stream and allow the camera sensor to warm up
print("[INFO] starting video stream...")
vs = VideoStream(src=0).start()
time.sleep(2.0)

# construct the argument parser and parse the arguments
def myTest():
	# loop over the frames from the video stream
	while True:
		# grab the frame from the threaded video stream and resize it
		# to have a maximum width of 400 pixels
		frame = vs.read()
		frame = cv2.flip(frame, 0)
		frame = imutils.resize(frame, width=500)

		# detect faces in the frame and determine if they are wearing a
		# face mask or not
		(locs, preds) = detect_and_predict_mask(frame, faceNet, maskNet, args)

		# loop over the detected face locations and their corresponding
		# locations
		withCounter = 0
		withoutCounter = 0
		for (box, pred) in zip(locs, preds):
			# unpack the bounding box and predictions
			(startX, startY, endX, endY) = box
			(mask, withoutMask) = pred

			# determine the class label and color we'll use to draw
			# the bounding box and text
			if mask > withoutMask:
				label = "Thank You. Mask On."
				color = (0, 255, 0)
				withCounter+=1

			else:
				label = "No Face Mask Detected"
				color = (0, 0, 255)
				global isAlarmActive
				withoutCounter+=1
				if(isAlarmActive and isViedoFeedActive):
					rainbowhat.buzzer.midi_note(60, 1)
			
			# display the label and bounding box rectangle on the output
			# frame
			cv2.putText(frame, label, (startX-50, startY - 10),
				cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
			cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)

		# show the output frame
		#global RGB_img
		RGB_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		if(not isViedoFeedActive):
			RGB_img = cv2.imread('./static/logo.jpeg', 0)
			rainbowhat.display.print_str('----')
		else:
			rainbowhat.display.print_str('0'+str(withCounter)+'0'+str(withoutCounter))
		global save_img
		save_img = RGB_img
		retValue, image = cv2.imencode('.jpg', RGB_img)
		
		rainbowhat.display.show()
		yield(decodeData(image.tobytes()))
		key = cv2.waitKey(1) & 0xFF

		# if the `q` key was pressed, break from the loop
		if key == ord("q"):
			break
	# do a bit of cleanup
	cv2.destroyAllWindows()
	vs.stop()

app = Flask(__name__)

@app.route('/')
def loadHTML():
    return render_template('index.html')


def decodeData(imageBytes):
    return (b'--frame\r\n Content-Type: image/jpeg\r\n\r\n' + imageBytes + b'\r\n\r\n')

@app.route('/alarm')
def alarm():
    global isAlarmActive
    isAlarmActive = not isAlarmActive
    return 'alarm'

@app.route('/picture')
def picture():
    global save_img
    cv2.imwrite('hallo.jpg', save_img)
    return 'picture'

@app.route('/activateViedoFeed')
def activateViedoFeed():
    global isViedoFeedActive
    isViedoFeedActive = True
    return 'activateViedoFeed'

@app.route('/disableViedoFeed')
def disableViedoFeed():
    global isViedoFeedActive
    isViedoFeedActive = False
    return 'disableViedoFeed'

@app.route('/video_feed')
def video_feed():
    return Response(myTest(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
