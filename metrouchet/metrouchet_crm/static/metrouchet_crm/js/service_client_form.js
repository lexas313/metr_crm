$(document).ready(function () {
    $('#service-formset').formset({
        addText: 'Добавить услугу',
        deleteText: 'Удалить услугу',
        prefix: 'service_form',
        addCssClass: 'text-success',
        deleteCssClass: 'text-danger',
        removed: function (row) {
            row.find('input[name$="DELETE"]').prop('checked', true);
        }
    });

    $('#add-service-form').on('click', function() {
        $('#service-formset').formset('addForm');
    });

        $('#client-formset').formset({
        addText: 'Добавить клиента',
        deleteText: 'Удалить клиента',
        prefix: 'client_form',
        addCssClass: 'text-success',
        deleteCssClass: 'text-danger',
        removed: function (row) {
            row.find('input[name$="DELETE"]').prop('checked', true);
        }
    });

    $('#add-client-form').on('click', function() {
        $('#client-formset').formset('addForm');
    });

});