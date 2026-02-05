const express = require('express');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const path = require('path');
const fs = require('fs');
const { Document, Packer, Paragraph, ImageRun, TextRun, PageBreak, ExternalHyperlink } = require('docx');

const app = express();
const port = 3000;

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// --- GLOBAL DEĞİŞKENLER ---
let globalBrowser = null;
let cachedCookies = null; 

function loadCookiesIntoMemory() {
    const cookiePath = path.join(__dirname, '../twitter_cookies.json');
    if (fs.existsSync(cookiePath)) {
        try {
            const cookiesString = fs.readFileSync(cookiePath, 'utf8');
            cachedCookies = JSON.parse(cookiesString);
            console.log(`✔ Çerezler yüklendi.`);
        } catch (e) { console.error("Çerez hatası:", e.message); }
    }
}
loadCookiesIntoMemory();

app.get('/', (req, res) => { res.sendFile(path.join(__dirname, 'public', 'index.html')); });

async function getBrowser() {
    if (globalBrowser && globalBrowser.isConnected()) return globalBrowser;
    console.log("Tarayıcı başlatılıyor...");
    globalBrowser = await puppeteer.launch({
        headless: "new",
        args: [
            '--no-sandbox', '--disable-setuid-sandbox',
            '--disable-dev-shm-usage', '--disable-accelerated-2d-canvas',
            '--disable-gpu', '--lang=tr-TR,tr'
        ]
    });
    return globalBrowser;
}

app.post('/generate-word', async (req, res) => {
    const { urls, jobId } = req.body;
    if (!urls || !urls.length) return res.status(400).json({ error: 'Link yok.' });

    loadCookiesIntoMemory();
    console.log(`${urls.length} link işleniyor... (İş: ${jobId})`);

    // Helper to update progress
    const updateProgress = (current, total, lastUrl) => {
        if (!jobId) return;

        // Ensure temp directory exists
        const tempDir = path.resolve(__dirname, '../temp');
        if (!fs.existsSync(tempDir)) {
            try {
                fs.mkdirSync(tempDir, { recursive: true });
            } catch (e) {
                console.error("Temp klasörü oluşturma hatası:", e);
                return;
            }
        }

        const progressPath = path.join(tempDir, `progress_${jobId}.json`);
        const status = {
            current: current,
            total: total,
            last_url: lastUrl,
            timestamp: Date.now()
        };
        try {
            fs.writeFileSync(progressPath, JSON.stringify(status));
        } catch (e) {
            console.error("Progress yazma hatası:", e);
        }
    };

    try {
        const browser = await getBrowser();
        const docChildren = [];
        
        docChildren.push(new Paragraph({
            children: [
                new TextRun({ text: "Twitter Raporu", bold: true, size: 32 }),
                new TextRun({ text: "\nTarih: " + new Date().toLocaleDateString("tr-TR"), size: 20, break: 1 })
            ], spacing: { after: 400 },
        }));
        
        for (let i = 0; i < urls.length; i++) {
            const url = urls[i];
            if(!url.trim()) continue;

            // Update progress start of item
            updateProgress(i + 1, urls.length, url);
            console.log(`[${i+1}/${urls.length}] ${url}`);
            
            if (i > 0 && i % 3 === 0) docChildren.push(new Paragraph({ children: [new PageBreak()] }));

            docChildren.push(new Paragraph({
                children: [
                    new TextRun({ text: "Link: ", bold: true }),
                    new ExternalHyperlink({
                        children: [ new TextRun({ text: url, style: "Hyperlink", color: "0563C1", underline: { type: "single" } }) ],
                        link: url,
                    }),
                ], spacing: { after: 200 },
            }));

            let page;
            try {
                page = await browser.newPage();
                
                // Gereksiz kaynakları engelle
                await page.setRequestInterception(true);
                page.on('request', (req) => {
                    const type = req.resourceType();
                    if (['font', 'media', 'websocket', 'manifest'].includes(type)) req.abort();
                    else req.continue(); 
                });

                await page.setExtraHTTPHeaders({ 'Accept-Language': 'tr-TR,tr;q=0.9' });
                await page.setViewport({ width: 1080, height: 1920 });

                if (cachedCookies) {
                    await page.setCookie(...cachedCookies);
                    await page.setCookie({ name: 'lang', value: 'tr', domain: '.x.com', path: '/', secure: true, sameSite: 'None' });
                }

                await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

                const isTweet = url.includes('/status/');
                let imageBuffer;
                let originalWidth = 0;
                let originalHeight = 0;

                if (isTweet) {
                    // --- TWEET MODU ---
                    const tweetSelector = 'article[data-testid="tweet"]';
                    await page.waitForSelector(tweetSelector, { timeout: 10000 });
                    
                    await page.evaluate(() => {
                         const stats = document.querySelector('article[data-testid="tweet"] div[role="group"]');
                         if(stats) stats.style.display = 'none';
                         const sidebar = document.querySelector('[data-testid="sidebarColumn"]');
                         if(sidebar) sidebar.style.display = 'none';
                    });

                    await new Promise(r => setTimeout(r, 1000));
                    
                    const tweetElement = await page.$(tweetSelector);
                    const box = await tweetElement.boundingBox();
                    if(box) {
                        originalWidth = box.width;
                        originalHeight = box.height;
                        imageBuffer = await tweetElement.screenshot();
                    }

                } else {
                    // --- PROFİL MODU (KESİN ÇÖZÜM) ---
                    const columnSelector = '[data-testid="primaryColumn"]';
                    await page.waitForSelector(columnSelector, { timeout: 15000 });
                    
                    // Görsel Bekleme
                    try {
                        await page.waitForFunction(() => {
                            const banner = document.querySelector('img[src*="profile_banners"]');
                            const avatar = document.querySelector('img[src*="profile_images"]');
                            return (banner && banner.complete) || (avatar && avatar.complete);
                        }, { timeout: 5000 });
                    } catch(e) {}

                    // --- TEMİZLİK OPERASYONU ---
                    await page.evaluate(() => {
                        window.killGreenBox = () => {
                            // 1. Yan Menüleri Gizle
                            const side = document.querySelector('[data-testid="sidebarColumn"]');
                            if(side) side.style.display = 'none';
                            const bottom = document.querySelector('[data-testid="placementTracking"]');
                            if(bottom) bottom.style.display = 'none';

                            // 2. BUTON HEDEFLEME (Yeşil Kutu İçin)
                            // "Onaylanmış Hesap Sahibi Ol" butonunu bulursak, onun ebeveynini yok ederiz.
                            // XPath kullanarak metin içeren elementi bulmak daha güvenilirdir.
                            const buttons = document.querySelectorAll('div[role="button"], span, div');
                            
                            buttons.forEach(el => {
                                // Sadece görünür elementlere bak
                                if(el.offsetParent === null) return;

                                const text = (el.innerText || "").toLowerCase();
                                if(text.includes("onaylanmış hesap sahibi ol") || 
                                   text.includes("get verified") ||
                                   text.includes("hesabın onaylı değil")) {

                                    // AMAN DİKKAT: Header veya Bio içindeyse DOKUNMA
                                    if(el.closest('[data-testid="UserProfileHeader_Items"]')) return;
                                    if(el.closest('[data-testid="UserDescription"]')) return;
                                    if(el.closest('[data-testid="UserName"]')) return;

                                    // Yeşil kutuyu bulmak için yukarı tırman
                                    let parent = el.closest('[data-testid="cellInnerDiv"]');
                                    
                                    // Eğer cellInnerDiv bulamazsa, 5 seviye yukarı çıkıp uygun div'i bul
                                    if(!parent) {
                                        let curr = el.parentElement;
                                        for(let i=0; i<6; i++) {
                                            if(curr && curr.tagName === 'DIV') {
                                                // Ana sütunu silmemek için kontrol
                                                const testId = curr.getAttribute('data-testid');
                                                if(testId !== 'primaryColumn' && testId !== 'UserProfileHeader_Items') {
                                                    // Yeşil kutu genellikle 200px'den küçüktür
                                                    if(curr.offsetHeight < 300) {
                                                        parent = curr;
                                                    }
                                                }
                                            }
                                            if(curr) curr = curr.parentElement;
                                        }
                                    }

                                    if(parent) {
                                        parent.style.setProperty('display', 'none', 'important');
                                        parent.setAttribute('data-deleted', 'true');
                                    }
                                }
                            });
                        };

                        // Sürekli kontrol et (3 saniye boyunca her 300ms'de bir)
                        let attempt = 0;
                        const interval = setInterval(() => {
                            window.killGreenBox();
                            attempt++;
                            if(attempt > 10) clearInterval(interval);
                        }, 300);
                        
                        window.killGreenBox(); // İlk vuruş
                    });

                    // Bekleme (Kutunun yüklenmesi ve silinmesi için)
                    await new Promise(r => setTimeout(r, 1500));

                    // --- KIRPMA (YEDEK PLAN) ---
                    // Eğer silme çalışmazsa, biz manuel olarak keseceğiz.
                    const columnElement = await page.$(columnSelector);
                    if (!columnElement) throw new Error("Profil yüklenemedi.");

                    const columnBox = await columnElement.boundingBox();
                    const tabsElement = await page.$('[role="tablist"]'); 
                    
                    // Takipçi sayısının olduğu element (En güvenli sınır noktası)
                    const statsElement = await page.$('[data-testid="UserProfileHeader_Items"]');

                    let finalCropHeight = columnBox.height;
                    let cutPointY = 0;

                    if (tabsElement) {
                        const tabsBox = await tabsElement.boundingBox();
                        if (tabsBox && columnBox && tabsBox.y > columnBox.y) {
                            cutPointY = tabsBox.y;
                        }
                    }

                    // EĞER Yeşil Kutu silinemediyse, Tabs ile Stats arasına girmiştir.
                    // Stats'in hemen altından kesersek kutuyu da kesmiş oluruz.
                    if (statsElement) {
                        const statsBox = await statsElement.boundingBox();
                        if (statsBox) {
                            // Stats'in alt noktası
                            const statsBottom = statsBox.y + statsBox.height;
                            
                            // Eğer Tabs ile Stats arasında çok boşluk varsa (örneğin > 50px), orada yeşil kutu vardır.
                            // O zaman Stats'in hemen altından (biraz pay bırakıp) keselim.
                            if (cutPointY > 0 && (cutPointY - statsBottom) > 60) {
                                console.log("Yeşil kutu tespit edildi (boşluktan), güvenli kesim yapılıyor.");
                                // Sadece 45px pay bırak, gerisini at.
                                cutPointY = statsBottom + 45; 
                            } else if (cutPointY === 0) {
                                // Tabs bulunamazsa Stats'e göre kes
                                cutPointY = statsBottom + 50;
                            }
                        }
                    }

                    if (cutPointY > columnBox.y) {
                        finalCropHeight = cutPointY - columnBox.y;
                    } else {
                        // Hiçbir referans bulamazsa varsayılan
                        finalCropHeight = Math.min(finalCropHeight, 900);
                    }
                    
                    // Güvenlik: Çok küçük kesmesin
                    if (finalCropHeight < 200) finalCropHeight = 800;

                    originalWidth = columnBox.width;
                    originalHeight = finalCropHeight;

                    imageBuffer = await page.screenshot({
                        clip: { 
                            x: columnBox.x, 
                            y: columnBox.y, 
                            width: originalWidth, 
                            height: originalHeight 
                        }
                    });
                }

                const MAX_WIDTH = 480;  
                const MAX_HEIGHT = 230; 
                let finalWidth = MAX_WIDTH;
                let finalHeight = (originalHeight / originalWidth) * MAX_WIDTH;
                
                if (finalHeight > MAX_HEIGHT) {
                    finalHeight = MAX_HEIGHT;
                    finalWidth = (originalWidth / originalHeight) * MAX_HEIGHT;
                }

                docChildren.push(new Paragraph({
                    children: [new ImageRun({ data: imageBuffer, transformation: { width: finalWidth, height: finalHeight } })],
                    spacing: { after: 0 },
                }));

            } catch (err) {
                console.error(`Hata (${url}):`, err.message);
                docChildren.push(new Paragraph({ children: [new TextRun({ text: "Hata: " + err.message, color: "FF0000" })] }));
            } finally {
                if (page) await page.close();
            }
        }

        const doc = new Document({ sections: [{ children: docChildren }] });
        const buffer = await Packer.toBuffer(doc);
        
        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
        res.setHeader('Content-Disposition', 'attachment; filename=twitter_raporu.docx');
        res.send(buffer);
        console.log("İşlem tamamlandı.");

        // Final cleanup
        if (jobId) {
             try {
                const progressPath = path.join(__dirname, '../temp', `progress_${jobId}.json`);
                if (fs.existsSync(progressPath)) fs.unlinkSync(progressPath);
             } catch(e) {}
        }

    } catch (error) {
        console.error('Sunucu Hatası:', error);
        res.status(500).json({ error: 'İşlem hatası.' });
    }
});

app.listen(port, () => { console.log(`Sunucu hazır: http://localhost:${port}`); });