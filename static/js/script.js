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
    cameraPlaceholder.style.display = 'block';
    cameraOverlay.style.display = 'none';
    
    startCameraBtn.style.display = 'flex';
    stopCameraBtn.style.display = 'none';
    cameraStatusText.style.display = 'none';
}

async function captureAndAnalyzeFrame() {
    if (!isCameraMonitoring) return;
    
    if (webcamVideo.videoWidth === 0 || isAnalyzing) {
        setTimeout(captureAndAnalyzeFrame, 500);
        return;
    }
    
    isAnalyzing = true;
    const context = captureCanvas.getContext('2d');
    captureCanvas.width = webcamVideo.videoWidth;
    captureCanvas.height = webcamVideo.videoHeight;
    context.drawImage(webcamVideo, 0, 0, captureCanvas.width, captureCanvas.height);
    
    // تحويل الصورة الى ملف وارسالها للواجهة البرمجية
    captureCanvas.toBlob(async (blob) => {
        const formData = new FormData();
        formData.append('file', blob, 'camera_frame.jpg');
        
        try {
            const response = await fetch('/api/predict', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (response.ok) {
                displayResult(data);
                
                // تحديث الشاشة العائمة على الكاميرا للنتيجة الفورية
                cameraOverlay.textContent = `النتيجة المباشرة: ${data.posture} (${data.confidence})`;
                if (data.is_alert) {
                    cameraOverlay.style.background = 'rgba(239, 68, 68, 0.9)'; // أحمر
                } else {
                    cameraOverlay.style.background = 'rgba(16, 185, 129, 0.9)'; // أخضر
                }
            }
        } catch (err) {
            console.error("Camera analysis error:", err);
        } finally {
            isAnalyzing = false;
            // تحليل الفريم التالي بعد ثانية واحدة لمنع الضغط على السيرفر
            if (isCameraMonitoring) {
                setTimeout(captureAndAnalyzeFrame, 1000);
            }
        }
    }, 'image/jpeg', 0.8);
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

    const formData = new FormData();
    const file = fileInput.files[0];
    formData.append('file', file);

    // 🔄 عرض مؤشر التحميل
    loader.classList.add('show');
    resultContainer.classList.remove('show');
    errorDiv.classList.remove('show');
    
    // تعطيل الأزرار
    predictBtn.disabled = true;
    
    try {
        // 📡 اختيار المسار الصحيح (صورة أو فيديو)
        let isVideo = false;
        if (file) {
            if (file.type && file.type.startsWith('video/')) {
                isVideo = true;
            } else {
                // احتياط: تحديد النوع من الامتداد في حال type فارغ
                const ext = file.name.split('.').pop().toLowerCase();
                const videoExts = ['mp4', 'avi', 'mov', 'mkv'];
                if (videoExts.includes(ext)) {
                    isVideo = true;
                }
            }
        }
        const endpoint = isVideo ? '/api/predict_video' : '/api/predict';

        // 📡 إرسال الطلب للخادم
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'خطأ في المعالجة');
        }
        
        // ✅ عرض النتيجة بشكل جميل
        displayResult(data);
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