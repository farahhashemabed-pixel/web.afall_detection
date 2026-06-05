// ==================== DOM Elements ====================
const fileInput = document.getElementById('fileInput');
const fileLabel = document.getElementById('fileLabel');
const fileName = document.getElementById('fileName');
const fileNameText = document.getElementById('fileNameText');
const predictBtn = document.getElementById('predictBtn');
const resetBtn = document.getElementById('resetBtn');
const loader = document.getElementById('loader');
const resultContainer = document.getElementById('resultContainer');
const resultCard = document.getElementById('resultCard');
const errorDiv = document.getElementById('errorDiv');
const errorMessage = document.getElementById('errorMessage');

// Camera Elements
const modeUploadBtn = document.getElementById('modeUploadBtn');
const modeCameraBtn = document.getElementById('modeCameraBtn');
const uploadSection = document.getElementById('uploadSection');
const cameraSection = document.getElementById('cameraSection');
const startCameraBtn = document.getElementById('startCameraBtn');
const stopCameraBtn = document.getElementById('stopCameraBtn');
const webcamVideo = document.getElementById('webcamVideo');
const captureCanvas = document.getElementById('captureCanvas');
const cameraPlaceholder = document.getElementById('cameraPlaceholder');
const cameraStatusText = document.getElementById('cameraStatusText');
const cameraOverlay = document.getElementById('cameraOverlay');

let cameraStream = null;
let captureInterval = null;
let isCameraMonitoring = false;

// ==================== Image Preview Elements ====================
const imagePreviewContainer = document.getElementById('imagePreviewContainer');
const imagePreview = document.getElementById('imagePreview');

// ==================== 1. تبديل وضعيات الرفع والمراقبة ====================
if (modeUploadBtn && modeCameraBtn) {
    modeUploadBtn.addEventListener('click', () => {
        modeUploadBtn.classList.replace('btn-reset', 'btn-predict');
        modeUploadBtn.classList.add('active');
        modeCameraBtn.classList.replace('btn-predict', 'btn-reset');
        modeCameraBtn.classList.remove('active');
        
        uploadSection.style.display = 'block';
        cameraSection.style.display = 'none';
        
        if (isCameraMonitoring) stopCamera();
    });

    modeCameraBtn.addEventListener('click', () => {
        modeCameraBtn.classList.replace('btn-reset', 'btn-predict');
        modeCameraBtn.classList.add('active');
        modeUploadBtn.classList.replace('btn-predict', 'btn-reset');
        modeUploadBtn.classList.remove('active');
        
        uploadSection.style.display = 'none';
        cameraSection.style.display = 'block';
    });
}

// ==================== 2. معالجة المراقبة الحية (الكاميرا) ====================
let isAnalyzing = false;

startCameraBtn.addEventListener('click', async () => {
    try {
        // الكاميرا الخلفية "environment" وعدم قلب الصورة
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { exact: "environment" } } });
    } catch (err) {
        try {
            // بديل: أي كاميرا خلفية متاحة
            cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        } catch (err2) {
            // بديل أخير: أي كاميرا
            cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
        }
    }
    
    try {
        webcamVideo.srcObject = cameraStream;
        webcamVideo.style.display = 'block';
        cameraPlaceholder.style.display = 'none';
        
        startCameraBtn.style.display = 'none';
        stopCameraBtn.style.display = 'flex';
        cameraStatusText.style.display = 'block';
        cameraOverlay.style.display = 'block';
        cameraOverlay.textContent = 'جاري التحليل...';
        
        isCameraMonitoring = true;
        isAnalyzing = false;
        resultContainer.classList.remove('show');
        errorDiv.classList.remove('show');
        
        // بدء حلقة التحليل المباشر بطريقة تمنع تداخل الطلبات إذا كان الإنترنت بطيئاً
        captureAndAnalyzeFrame();
        
    } catch (err) {
        showError('فشل عرض الكاميرا.');
        console.error(err);
    }
});

stopCameraBtn.addEventListener('click', () => {
    stopCamera();
});

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
    }
    isCameraMonitoring = false;
    isAnalyzing = false;
    
    webcamVideo.style.display = 'none';
    const processedImg = document.getElementById('webcamProcessedImg');
    if (processedImg) {
        processedImg.style.display = 'none';
        processedImg.src = '';
    }
    cameraPlaceholder.style.display = 'block';
    cameraOverlay.style.display = 'none';
    
    startCameraBtn.style.display = 'flex';
    stopCameraBtn.style.display = 'none';
    cameraStatusText.style.display = 'none';
}

async function captureAndAnalyzeFrame() {
    if (!isCameraMonitoring) return;
    
    if (webcamVideo.videoWidth === 0 || isAnalyzing) {
        setTimeout(captureAndAnalyzeFrame, 200);
        return;
    }
    
    isAnalyzing = true;
    
    try {
        // تشغيل كاشف الوضعيات وتحديد أجزاء الجسم ورسمها على الكانفاس محلياً
        const analysis = await processPoseOnCanvas(webcamVideo, captureCanvas);
        
        // عرض النتيجة المرسومة فوراً للمستخدم للحصول على بث فائق السرعة
        const processedImg = document.getElementById('webcamProcessedImg');
        if (processedImg) {
            processedImg.src = captureCanvas.toDataURL('image/jpeg', 0.85);
            processedImg.style.display = 'block';
            webcamVideo.style.display = 'none';
        }
        
        // تحديث النص العائم مباشرة
        cameraOverlay.style.display = 'block';
        cameraOverlay.textContent = `النتيجة المباشرة: ${analysis.posture} (${(analysis.confidence * 100).toFixed(1)}%)`;
        if (analysis.posture === 'سقوط') {
            cameraOverlay.style.background = 'rgba(239, 68, 68, 0.9)'; // أحمر
        } else if (analysis.posture === 'جالس') {
            cameraOverlay.style.background = 'rgba(245, 158, 11, 0.9)'; // برتقالي
        } else {
            cameraOverlay.style.background = 'rgba(16, 185, 129, 0.9)'; // أخضر
        }
        
        // إرسال الصورة المرسومة والنتيجة للسيرفر كل 1.5 ثانية لحفظ الإحصاءات وإرسال التنبيهات
        captureCanvas.toBlob(async (blob) => {
            if (!blob) {
                isAnalyzing = false;
                if (isCameraMonitoring) setTimeout(captureAndAnalyzeFrame, 500);
                return;
            }
            
            const formData = new FormData();
            formData.append('file', blob, 'camera_frame.jpg');
            formData.append('posture', analysis.posture);
            formData.append('confidence', `${(analysis.confidence * 100).toFixed(1)}%`);
            
            try {
                const response = await fetch('/api/predict', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (response.ok) {
                    displayResult(data);
                }
            } catch (err) {
                console.error("Server update error:", err);
            } finally {
                isAnalyzing = false;
                if (isCameraMonitoring) {
                    setTimeout(captureAndAnalyzeFrame, 1500);
                }
            }
        }, 'image/jpeg', 0.85);
        
    } catch (err) {
        console.error("Camera analysis error:", err);
        isAnalyzing = false;
        if (isCameraMonitoring) {
            setTimeout(captureAndAnalyzeFrame, 1000);
        }
    }
}

// ==================== 3. معالجة تحميل الملف (صورة / فيديو) ====================
fileInput.addEventListener('change', function(e) {
    if (e.target.files.length > 0) {
        const file = e.target.files[0];
        
        // تحديث الواجهة - اسم الملف
        const name = file.name;
        fileNameText.textContent = name;
        fileName.classList.add('show');
        predictBtn.disabled = false;
        errorDiv.classList.remove('show');
        
        // ✅ معاينة فقط إذا كان الملف صورة
        if (file.type && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(ev) {
                imagePreview.src = ev.target.result;
                imagePreviewContainer.style.display = 'block';
            };
            reader.readAsDataURL(file);
        } else {
            // إخفاء المعاينة في حالة الفيديو
            imagePreviewContainer.style.display = 'none';
            imagePreview.src = '';
        }
    }
});

// ==================== 4. السحب والإفلات ====================
fileLabel.addEventListener('dragover', function(e) {
    e.preventDefault();
    fileLabel.classList.add('dragover');
});

fileLabel.addEventListener('dragleave', function(e) {
    fileLabel.classList.remove('dragover');
});

fileLabel.addEventListener('drop', function(e) {
    e.preventDefault();
    fileLabel.classList.remove('dragover');
    
    if (e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        
        // تعيين الملف إلى input
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;
        
        // تحديث الواجهة
        fileNameText.textContent = file.name;
        fileName.classList.add('show');
        predictBtn.disabled = false;
        errorDiv.classList.remove('show');
        
        // ✅ معاينة فقط إذا كان الملف صورة
        if (file.type && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(ev) {
                imagePreview.src = ev.target.result;
                imagePreviewContainer.style.display = 'block';
            };
            reader.readAsDataURL(file);
        } else {
            imagePreviewContainer.style.display = 'none';
            imagePreview.src = '';
        }
    }
});

// ==================== 5. إرسال الصورة للنموذج ====================
predictBtn.addEventListener('click', async function() {
    if (!fileInput.files || fileInput.files.length === 0) {
        showError('الرجاء اختيار صورة أو فيديو أولاً');
        return;
    }

    const file = fileInput.files[0];
    loader.classList.add('show');
    resultContainer.classList.remove('show');
    errorDiv.classList.remove('show');
    predictBtn.disabled = true;
    
    try {
        let isVideo = false;
        if (file) {
            if (file.type && file.type.startsWith('video/')) {
                isVideo = true;
            } else {
                const ext = file.name.split('.').pop().toLowerCase();
                const videoExts = ['mp4', 'avi', 'mov', 'mkv'];
                if (videoExts.includes(ext)) {
                    isVideo = true;
                }
            }
        }

        const formData = new FormData();
        
        if (isVideo) {
            formData.append('file', file);
            const response = await fetch('/api/predict_video', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'خطأ في معالجة الفيديو');
            displayResult(data);
        } else {
            // للتأكد من اكتمال تحميل الصورة للمعاينة
            if (!imagePreview.complete || imagePreview.naturalWidth === 0) {
                await new Promise((resolve) => {
                    imagePreview.onload = resolve;
                });
            }
            
            // محاولة تشغيل كشف الوضعيات محلياً بـ MediaPipe
            let analysis = null;
            let useClientSide = false;
            try {
                const tempCanvas = document.createElement('canvas');
                analysis = await processPoseOnCanvas(imagePreview, tempCanvas);
                
                // إذا نجح MediaPipe في كشف شخص
                if (analysis && analysis.confidence > 0) {
                    useClientSide = true;
                    imagePreview.src = tempCanvas.toDataURL('image/jpeg', 0.85);
                    
                    await new Promise((resolve, reject) => {
                        tempCanvas.toBlob(async (blob) => {
                            if (!blob) { reject(new Error('فشل تحليل الصورة')); return; }
                            formData.append('file', blob, 'uploaded_frame.jpg');
                            formData.append('posture', analysis.posture);
                            formData.append('confidence', `${(analysis.confidence * 100).toFixed(1)}%`);
                            try {
                                const response = await fetch('/api/predict', { method: 'POST', body: formData });
                                const data = await response.json();
                                if (!response.ok) throw new Error(data.error || 'خطأ');
                                displayResult(data);
                                resolve();
                            } catch (err) { reject(err); }
                        }, 'image/jpeg', 0.85);
                    });
                }
            } catch (e) {
                console.log('MediaPipe failed, falling back to server:', e);
                useClientSide = false;
            }
            
            // إذا فشل MediaPipe في كشف الشخص، نرسل الصورة الأصلية للسيرفر ليحللها
            if (!useClientSide) {
                formData.append('file', file);
                const response = await fetch('/api/predict', { method: 'POST', body: formData });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'خطأ في معالجة الصورة');
                if (data.processed_image) {
                    imagePreview.src = `data:image/jpeg;base64,${data.processed_image}`;
                }
                displayResult(data);
            }
        }
    } catch (error) {
        showError(error.message);
    } finally {
        loader.classList.remove('show');
        predictBtn.disabled = false;
        resetBtn.style.display = 'flex';
    }
});

// ==================== 6. عرض النتيجة بألوان مختلفة ====================
function displayResult(data) {
    const posture = data.posture;
    const confidence = parseFloat(data.confidence);
    
    // تحديد اللون حسب النتيجة
    const postureInfo = {
        'جالس': { 
            icon: '👤', 
            title: '✅ وضعية آمنة', 
            subtitle: 'الشخص في وضعية جلوس طبيعية',
            class: 'success'
        },
        'واقف': { 
            icon: '🚶', 
            title: '✅ وضعية آمنة', 
            subtitle: 'الشخص في وضعية وقوف طبيعية',
            class: 'success'
        },
        'ممدد': { 
            icon: '🛏️', 
            title: '⚠️ تحذير', 
            subtitle: 'الشخص في وضعية استلقاء',
            class: 'warning'
        },
        'سقوط': { 
            icon: '⚠️', 
            title: '🚨 تنبيه طوارئ', 
            subtitle: 'تم اكتشاف سقوط محتمل!',
            class: 'alert'
        }
    };

    const info = postureInfo[posture] || { 
        icon: '❓', 
        title: 'غير معروف', 
        subtitle: 'لم يتم تحديد الوضعية',
        class: 'warning' 
    };

    // تحديث البطاقة
    resultCard.className = `result-card ${info.class}`;
    document.getElementById('resultIcon').textContent = info.icon;
    document.getElementById('resultTitle').textContent = info.title;
    document.getElementById('resultSubtitle').textContent = info.subtitle;
    document.getElementById('posture').textContent = posture;
    document.getElementById('confidence').textContent = confidence.toFixed(2) + '%';
    document.getElementById('alertStatus').textContent = data.is_alert ? '⚠️ تنبيه نشط' : '✅ آمن';
    document.getElementById('description').textContent = data.description;
    
    // تحديث شريط الثقة
    const confidenceFill = document.getElementById('confidenceFill');
    confidenceFill.style.width = confidence + '%';
    document.getElementById('confidencePercent').textContent = confidence.toFixed(2) + '%';
    
    // عدد الفريمات وتفاصيلها في حالة الفيديو
    const framesCountEl = document.getElementById('framesCount');
    const eventsContainer = document.getElementById('videoEventsContainer');
    const eventsList = document.getElementById('videoEventsList');
    const framesGalleryContainer = document.getElementById('framesGalleryContainer');
    const framesGallery = document.getElementById('framesGallery');

    if (data.events && Array.isArray(data.events) && data.events.length > 0) {
        if (framesCountEl) {
            framesCountEl.textContent = data.frames_count !== undefined
                ? data.frames_count
                : data.events.length;
        }

        if (eventsContainer && eventsList) {
            eventsContainer.style.display = 'block';
            eventsList.innerHTML = '';

            data.events.forEach(ev => {
                const li = document.createElement('li');
                const confPercent = (ev.confidence * 100).toFixed(1);
                li.textContent = `⏱ ثانية ${ev.time_sec} – ${ev.posture} (${confPercent}%)`;
                eventsList.appendChild(li);
            });
        }

        // إنشاء معرض الصور للفريمات
        if (framesGalleryContainer && framesGallery) {
            framesGalleryContainer.style.display = 'block';
            framesGallery.innerHTML = '';

            data.events.forEach((ev, index) => {
                if (!ev.image_data) return;
                const wrapper = document.createElement('div');
                wrapper.className = 'frame-item';

                const img = document.createElement('img');
                img.src = `data:image/jpeg;base64,${ev.image_data}`;
                img.alt = `Frame ${index + 1}`;

                const caption = document.createElement('div');
                caption.className = 'frame-caption';
                const confPercent = (ev.confidence * 100).toFixed(1);
                caption.textContent = `ث ${ev.time_sec} – ${ev.posture} (${confPercent}%)`;

                wrapper.appendChild(img);
                wrapper.appendChild(caption);
                framesGallery.appendChild(wrapper);
            });
        }
    } else {
        if (framesCountEl) {
            framesCountEl.textContent = '-';
        }
        if (eventsContainer && eventsList) {
            eventsContainer.style.display = 'none';
            eventsList.innerHTML = '';
        }
        if (framesGalleryContainer && framesGallery) {
            framesGalleryContainer.style.display = 'none';
            framesGallery.innerHTML = '';
        }
    }

    // عرض النتائج
    resultContainer.classList.add('show');

    // تشغيل صوت التنبيه عند اكتشاف السقوط بشكل سريع
    if (data.is_alert) {
        if (!window.alertTimeout) {
            playAlertSound();
            // منع تكرار الصوت المزعج في الكاميرا، السماح بصوت كل 5 ثوان
            window.alertTimeout = setTimeout(() => { window.alertTimeout = null; }, 5000);
        }
    }
}

// ==================== 7. دالة عرض الأخطاء ====================
function showError(message) {
    errorMessage.textContent = message;
    errorDiv.classList.add('show');
}

// ==================== 8. زر الصورة الجديدة ====================
resetBtn.addEventListener('click', function() {
    // إعادة تعيين الملفات
    fileInput.value = '';
    fileNameText.textContent = '';
    fileName.classList.remove('show');
    
    // إعادة تعيين الأزرار
    predictBtn.disabled = true;
    resetBtn.style.display = 'none';
    
    // إخفاء المعاينة والنتائج
    imagePreviewContainer.style.display = 'none';
    resultContainer.classList.remove('show');
    loader.classList.remove('show');
    errorDiv.classList.remove('show');
    
    // فتح نافذة اختيار الملف مباشرة
    fileInput.click();
});

// ==================== 9. تشغيل صوت التنبيه ====================
function playAlertSound() {
    // إنشاء صوت تنبيه بسيط باستخدام Web Audio API
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.value = 1000;
    oscillator.type = 'sine';
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.5);
}

// ==================== 10. تهيئة MediaPipe Pose وطرق المعالجة محلياً ====================
let pose = null;
let poseInitialized = false;

function initPose() {
    if (poseInitialized) return;
    try {
        pose = new Pose({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
            }
        });
        pose.setOptions({
            modelComplexity: 1,
            smoothLandmarks: true,
            enableSegmentation: false,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });
        poseInitialized = true;
        console.log("MediaPipe Pose initialized successfully!");
    } catch (err) {
        console.error("Failed to initialize MediaPipe Pose:", err);
    }
}

let poseResolve = null;
function getPoseResult(imageElement) {
    initPose();
    return new Promise((resolve) => {
        poseResolve = resolve;
        pose.onResults((results) => {
            if (poseResolve) {
                poseResolve(results);
                poseResolve = null;
            }
        });
        pose.send({ image: imageElement }).catch(err => {
            console.error("Pose send error:", err);
            resolve(null);
        });
    });
}

const poseConnections = [
    [11, 12], // shoulder to shoulder
    [11, 23], [12, 24], // shoulder to hip
    [23, 24], // hip to hip
    [11, 13], [13, 15], // left arm
    [12, 14], [14, 16], // right arm
    [23, 25], [25, 27], // left leg
    [24, 26], [26, 28]  // right leg
];

function drawSkeleton(ctx, landmarks, color, width, height) {
    ctx.save();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.75)";
    ctx.shadowColor = color;
    ctx.shadowBlur = 6;
    
    poseConnections.forEach(([i, j]) => {
        let pt1 = landmarks[i];
        let pt2 = landmarks[j];
        if (pt1 && pt2 && pt1.visibility > 0.5 && pt2.visibility > 0.5) {
            ctx.beginPath();
            ctx.moveTo(pt1.x * width, pt1.y * height);
            ctx.lineTo(pt2.x * width, pt2.y * height);
            ctx.stroke();
        }
    });
    
    // رسم المفاصل الرئيسية
    landmarks.forEach((pt, index) => {
        const mainJoints = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28];
        if (mainJoints.includes(index) && pt && pt.visibility > 0.5) {
            ctx.beginPath();
            ctx.arc(pt.x * width, pt.y * height, 5, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 2;
            ctx.fill();
            ctx.stroke();
        }
    });
    ctx.restore();
}

function drawRoundRect(ctx, x, y, w, h, r) {
    if (ctx.roundRect) {
        ctx.roundRect(x, y, w, h, r);
    } else {
        let radius = r;
        if (Array.isArray(r)) radius = r[0] || 0;
        if (w < 2 * radius) radius = w / 2;
        if (h < 2 * radius) radius = h / 2;
        ctx.moveTo(x + radius, y);
        ctx.arcTo(x + w, y, x + w, y + h, radius);
        ctx.arcTo(x + w, y + h, x, y + h, radius);
        ctx.arcTo(x, y + h, x, y, radius);
        ctx.arcTo(x, y, x + w, y, radius);
    }
}

function drawBodyPartBox(ctx, landmarks, indices, label, color, width, height) {
    let pts = indices.map(i => landmarks[i]).filter(p => p && p.visibility > 0.45);
    if (pts.length === 0) return;
    
    let minX = Math.min(...pts.map(p => p.x));
    let maxX = Math.max(...pts.map(p => p.x));
    let minY = Math.min(...pts.map(p => p.y));
    let maxY = Math.max(...pts.map(p => p.y));
    
    let pxMin = minX * width;
    let pxMax = maxX * width;
    let pyMin = minY * height;
    let pyMax = maxY * height;
    
    let w = pxMax - pxMin;
    let h = pyMax - pyMin;
    
    let padX = Math.max(w * 0.15, 12);
    let padY = Math.max(h * 0.15, 12);
    
    pxMin -= padX;
    pxMax += padX;
    pyMin -= padY;
    pyMax += padY;
    w = pxMax - pxMin;
    h = pyMax - pyMin;
    
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    
    ctx.beginPath();
    drawRoundRect(ctx, pxMin, pyMin, w, h, 8);
    ctx.stroke();
    
    ctx.fillStyle = color.replace('rgb', 'rgba').replace(')', ', 0.12)');
    ctx.fill();
    
    ctx.fillStyle = color;
    ctx.shadowBlur = 0;
    ctx.font = "bold 11px sans-serif";
    
    let textW = ctx.measureText(label).width;
    ctx.beginPath();
    drawRoundRect(ctx, pxMin, pyMin - 18, textW + 10, 18, [4, 4, 0, 0]);
    ctx.fill();
    
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, pxMin + 5, pyMin - 5);
    
    ctx.restore();
}

function getDistance(pt1, pt2) {
    return Math.sqrt(Math.pow(pt1.x - pt2.x, 2) + Math.pow(pt1.y - pt2.y, 2));
}

function getAngle(a, b, c) {
    let ab = {x: a.x - b.x, y: a.y - b.y};
    let cb = {x: c.x - b.x, y: c.y - b.y};
    let dot = ab.x * cb.x + ab.y * cb.y;
    let mag_ab = Math.sqrt(ab.x * ab.x + ab.y * ab.y);
    let mag_cb = Math.sqrt(cb.x * cb.x + cb.y * cb.y);
    let cosAngle = dot / (mag_ab * mag_cb);
    cosAngle = Math.max(-1, Math.min(1, cosAngle));
    return Math.acos(cosAngle) * 180 / Math.PI;
}

function classifyPose(landmarks, width, height) {
    if (!landmarks || landmarks.length < 29) {
        return { posture: 'غير معروف', confidence: 0.5 };
    }
    
    let nose = landmarks[0];
    let l_shoulder = landmarks[11];
    let r_shoulder = landmarks[12];
    let l_hip = landmarks[23];
    let r_hip = landmarks[24];
    let l_knee = landmarks[25];
    let r_knee = landmarks[26];
    let l_ankle = landmarks[27];
    let r_ankle = landmarks[28];
    
    let shoulder_center = {
        x: (l_shoulder.x + r_shoulder.x) / 2,
        y: (l_shoulder.y + r_shoulder.y) / 2
    };
    let hip_center = {
        x: (l_hip.x + r_hip.x) / 2,
        y: (l_hip.y + r_hip.y) / 2
    };
    let knee_center = {
        x: (l_knee.x + r_knee.x) / 2,
        y: (l_knee.y + r_knee.y) / 2
    };
    let ankle_center = {
        x: (l_ankle.x + r_ankle.x) / 2,
        y: (l_ankle.y + r_ankle.y) / 2
    };
    
    let allX = landmarks.map(l => l.x);
    let allY = landmarks.map(l => l.y);
    let minX = Math.min(...allX);
    let maxX = Math.max(...allX);
    let minY = Math.min(...allY);
    let maxY = Math.max(...allY);
    
    let bodyW = (maxX - minX) * width;
    let bodyH = (maxY - minY) * height;
    let aspect_ratio = bodyW / bodyH;
    
    let torso_dx = (shoulder_center.x - hip_center.x) * width;
    let torso_dy = (shoulder_center.y - hip_center.y) * height;
    let torso_angle = Math.abs(Math.atan2(torso_dy, torso_dx) * 180 / Math.PI); // 0 = flat, 90 = vertical
    
    let leftKneeAngle = getAngle(l_hip, l_knee, l_ankle);
    let rightKneeAngle = getAngle(r_hip, r_knee, r_ankle);
    let avgKneeAngle = (leftKneeAngle + rightKneeAngle) / 2;
    
    let leftHipAngle = getAngle(l_shoulder, l_hip, l_knee);
    let rightHipAngle = getAngle(r_shoulder, r_hip, r_knee);
    let avgHipAngle = (leftHipAngle + rightHipAngle) / 2;
    
    // Fallback if shoulder/hip are not visible
    if ((l_shoulder.visibility < 0.45 && r_shoulder.visibility < 0.45) || (l_hip.visibility < 0.45 && r_hip.visibility < 0.45)) {
        if (aspect_ratio < 0.55) {
            return { posture: 'واقف', confidence: 0.80 };
        } else if (aspect_ratio < 1.05) {
            return { posture: 'جالس', confidence: 0.80 };
        } else {
            return { posture: 'سقوط', confidence: 0.85 };
        }
    }
    
    let posture = 'واقف';
    let confidence = 0.95;
    
    // قواعد التصنيف باستخدام زوايا المفاصل ووضعية الجذع
    let isFallen = false;
    if (aspect_ratio > 1.1) {
        isFallen = true;
        confidence = 0.98;
    } else if (torso_angle < 35) {
        isFallen = true;
        confidence = 0.96;
    } else if (Math.abs(shoulder_center.y - hip_center.y) < 0.14 && aspect_ratio > 0.72) {
        isFallen = true;
        confidence = 0.92;
    }
    
    if (isFallen) {
        posture = 'سقوط';
    } else {
        let kneesBent = (leftKneeAngle < 135 || rightKneeAngle < 135);
        let hipsBent = (leftHipAngle < 135 || rightHipAngle < 135);
        
        if (kneesBent && hipsBent) {
            posture = 'جالس';
            confidence = 0.94;
        } else if (aspect_ratio >= 0.52 && torso_angle < 75) {
            posture = 'جالس';
            confidence = 0.88;
        } else {
            posture = 'واقف';
            confidence = 0.96;
        }
    }
    
    return { posture, confidence };
}

async function processPoseOnCanvas(sourceElement, canvasElement) {
    const results = await getPoseResult(sourceElement);
    const ctx = canvasElement.getContext('2d');
    
    let w = sourceElement.videoWidth || sourceElement.naturalWidth || sourceElement.width || 640;
    let h = sourceElement.videoHeight || sourceElement.naturalHeight || sourceElement.height || 480;
    
    if (w === 0 || h === 0) {
        w = 640;
        h = 480;
    }
    
    canvasElement.width = w;
    canvasElement.height = h;
    
    ctx.drawImage(sourceElement, 0, 0, w, h);
    
    if (results && results.poseLandmarks) {
        const landmarks = results.poseLandmarks;
        const analysis = classifyPose(landmarks, w, h);
        
        let color = "rgb(16, 185, 129)"; // أخضر للوقوف
        if (analysis.posture === 'جالس') {
            color = "rgb(245, 158, 11)"; // برتقالي للجلوس
        } else if (analysis.posture === 'سقوط') {
            color = "rgb(239, 68, 68)"; // أحمر للسقوط
        }
        
        // رسم مربعات أجزاء الجسم التفصيلية
        drawBodyPartBox(ctx, landmarks, [0,1,2,3,4,5,6,7,8,9,10], "الرأس - Head", color, w, h);
        drawBodyPartBox(ctx, landmarks, [11,12,23,24], "الجذع - Torso", color, w, h);
        drawBodyPartBox(ctx, landmarks, [11,13,15], "الذراع الأيسر - L Arm", color, w, h);
        drawBodyPartBox(ctx, landmarks, [12,14,16], "الذراع الأيمن - R Arm", color, w, h);
        drawBodyPartBox(ctx, landmarks, [23,25], "الفخذ الأيسر - L Thigh", color, w, h);
        drawBodyPartBox(ctx, landmarks, [24,26], "الفخذ الأيمن - R Thigh", color, w, h);
        drawBodyPartBox(ctx, landmarks, [25,27,29,31], "الساق اليسرى - L Shin", color, w, h);
        drawBodyPartBox(ctx, landmarks, [26,28,30,32], "الساق اليمنى - R Shin", color, w, h);
        
        // رسم الهيكل العظمي
        drawSkeleton(ctx, landmarks, color, w, h);
        
        return analysis;
    } else {
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 20px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("لم يتم كشف شخص في الإطار", w/2, h/2);
        return { posture: 'لم يتم كشف شخص', confidence: 0.0 };
    }
}