/* ============================================================
   FlaskToolkit 登出页：调用登出接口 + 自动/手动跳转
   ============================================================ */
(function () {
    'use strict';

    function init() {
        // 调用后端登出接口，确保 Cookie 被清除
        FT.doLogout({ redirect: '/login' });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
