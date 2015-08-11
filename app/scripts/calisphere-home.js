'use strict';

$(document).ready(function() {
  $('html').removeClass('no-jquery');
  
  $(document).on('submit', '#js-searchForm, #js-homeForm, #js-footerSearch', function() {
    sessionStorage.setItem('q', $(this).find('input').val());
  });
});