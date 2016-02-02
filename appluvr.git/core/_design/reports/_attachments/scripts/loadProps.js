var props = (function () {
    var props = null;
    $.ajax({
        'async': false,
        'cache': false,
        'global': false,
        'url': "data/props.json",
        'dataType': "json",
        'success': function (data) {
            props = data;
        }
    });
    return props;
})();