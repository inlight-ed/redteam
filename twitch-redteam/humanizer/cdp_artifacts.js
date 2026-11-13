// Базовая маскировка артефактов автоматизации
(() => {
    const strip = (obj, prop) => {
        try {
            Object.defineProperty(obj, prop, { get: () => undefined, configurable: true });
        } catch (e) {}
    };
    strip(navigator, 'webdriver');
    strip(window, 'cdc_adoQ425bcd421573312');
    strip(window, '__selenium_unwrapped');
    strip(window, '__webdriver_evaluate');
    strip(window, '__driver_evaluate');
    strip(window, 'callPhantom');
    strip(window, 'domAutomation');
    
    // Маскировка toString для нативных функций
    const nativeToString = Function.prototype.toString;
    Function.prototype.toString = function() {
        if (this.name === 'get' || this.name === 'set') {
            return 'function get ' + this.name + '() { [native code] }';
        }
        return nativeToString.call(this);
    };
})();
