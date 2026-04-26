from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

JS_PATCH = """
(function () {
    console.log("[YT-ADBLOCK] injected");

    function cleanAds(obj) {
        if (!obj || typeof obj   !== "object") return obj;

        try {
            delete obj.adPlacements;
            delete obj.playerAds;
            delete obj.adSlots;

            if (obj.playerResponse) {
                delete obj.playerResponse.adPlacements;
                delete obj.playerResponse.playerAds;
            }
        } catch (e) {}

        return obj;
    }

    // 🔥 patch JSON.parse zamiast fetch
    const origParse = JSON.parse;

    JSON.parse = function (...args) {
        const result = origParse.apply(this, args);

        try {
            // heurystyka: player response
            if (
                result &&
                typeof result === "object" &&
                (
                    result.streamingData ||
                    result.videoDetails ||
                    result.playabilityStatus
                )
            ) {
                return cleanAds(result);
            }
        } catch (e) {}

        return result;
    };

    // --- AUTO SKIP ---
    setInterval(() => {
        try {
            const skipBtn = document.querySelector(".ytp-ad-skip-button");
            if (skipBtn) skipBtn.click();

            const adShowing = document.querySelector(".ad-showing");
            const video = document.querySelector("video");

            if (adShowing && video) {
                video.currentTime = 9999;
            }
        } catch (e) {}
    }, 500);

    // --- CSS ---
    function injectCSS() {
        const style = document.createElement("style");
        style.textContent = `
            .ytp-ad-module,
            .ytp-ad-overlay-container,
            .ytp-ad-player-overlay,
            .video-ads,
            .ytp-ad-image-overlay {
                display: none !important;
            }
        `;
    
        if (document.head) {
            document.head.appendChild(style);
        } else if (document.documentElement) {
            document.documentElement.appendChild(style);
        }
    }

    // jeśli DOM już jest
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", injectCSS);
    } else {
        injectCSS();
    }

})();
"""

class AdBlocker(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl().toString()

        blocked = [
            "doubleclick.net",
            "googleads.g.doubleclick.net",
            "/api/stats/ads",
            "pagead"
        ]

        if any(b in url for b in blocked):
            info.block(True)
