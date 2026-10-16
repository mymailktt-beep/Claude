import sys,json,cv2,mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
S=sys.argv[1];frames=[int(x) for x in sys.argv[2].split(',')] if len(sys.argv)>2 and sys.argv[2] else None
pose=vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=S+'/pose_landmarker_heavy.task'),running_mode=vision.RunningMode.VIDEO,min_pose_detection_confidence=0.3,min_tracking_confidence=0.3))
hand=vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=S+'/hand_landmarker.task'),running_mode=vision.RunningMode.VIDEO,num_hands=2,min_hand_detection_confidence=0.3,min_tracking_confidence=0.3))
import os
fs=sorted(os.listdir(S+'/vid30'))
out=[]
for i,f in enumerate(fs):
    n=i+1
    if frames and n not in frames:continue
    img=cv2.cvtColor(cv2.imread(S+'/vid30/'+f),cv2.COLOR_BGR2RGB);h,w=img.shape[:2]
    im=mp.Image(image_format=mp.ImageFormat.SRGB,data=img);ts=int(i*1000/30)
    p=pose.detect_for_video(im,ts);hh=hand.detect_for_video(im,ts)
    rec={'n':n,'t':i/30}
    if p.pose_landmarks:
        L=p.pose_landmarks[0];rec['pose']={k:[L[j].x*w,L[j].y*h,L[j].visibility] for k,j in [('ls',11),('rs',12),('le',13),('re',14),('lw',15),('rw',16),('li',19),('ri',20)]}
    rec['hands']=[{'side':hd[0].category_name,'score':hd[0].score,'wrist':[lm[0].x*w,lm[0].y*h],'index_tip':[lm[8].x*w,lm[8].y*h],'mid_mcp':[lm[9].x*w,lm[9].y*h]} for hd,lm in zip(hh.handedness,hh.hand_landmarks)]
    out.append(rec)
json.dump(out,open(S+'/'+(sys.argv[3] if len(sys.argv)>3 else 'track.json'),'w'))
print(len(out))
