/*global _, QueryManager, GlobalSearchForm, FacetForm, CarouselContext, ComplexCarousel */

'use strict'; 

if(typeof console === 'undefined') {
  console = { log: function() { } };
}

$(document).on('pjax:timeout', function() { return false; });

var qm, globalSearchForm, facetForm, carousel, complexCarousel, DESKTOP;

var setupObjects = function() {
  if ($('#js-facet').length > 0) {
    if (facetForm === undefined) {
      facetForm = new FacetForm({model: qm});
      facetForm.listening = true;
    }
    else if (facetForm.listening === false) {
      facetForm.initialize();
      facetForm.delegateEvents();
      facetForm.listening = true;
    }
    facetForm.toggleSelectDeselectAll();

    // get rid of any visible tooltips
    var visibleTooltips = $('[data-toggle="tooltip"][aria-describedby]');
    for (var i=0; i<visibleTooltips.length; i++) {
      var tooltipId = $(visibleTooltips[i]).attr('aria-describedby');
      $('#' + tooltipId).remove();
    }
    // set tooltips
    $('[data-toggle="tooltip"]').tooltip({
      placement: 'top'
    });
  }
  else if (facetForm !== undefined) {
    facetForm.stopListening();
    facetForm.undelegateEvents();
    facetForm.listening = false;
  }

  if($('#js-carouselContainer').length > 0) {
    if (carousel === undefined) {
      carousel = new CarouselContext({model: qm});
      carousel.listening = true;
    }
    else if (carousel.listening === false) {
      carousel.initialize();
      carousel.delegateEvents();
      carousel.listening = true;
    }
  }
  else if (carousel !== undefined) {
    carousel.stopListening();
    carousel.undelegateEvents();
    carousel.listening = false;
  }

  if($('.carousel-complex').length > 0) {
    if (complexCarousel === undefined) {
      complexCarousel = new ComplexCarousel({model: qm});
      $('.js-obj__osd-infobanner').show();
      complexCarousel.listening = true;
    }
    else if (complexCarousel.listening === false) {
      complexCarousel.initialize();
      complexCarousel.delegateEvents();
      $('.js-obj__osd-infobanner').show();
      complexCarousel.listening = true;
    } else {
      $('.js-obj__osd-infobanner').hide();
      complexCarousel.initialize();
    }
    //TODO: this should only have to happen once!
    $('.js-obj__osd-infobanner-link').click(function(){
      $('.js-obj__osd-infobanner').slideUp('fast');
    });
  }
  else if (complexCarousel !== undefined) {
    complexCarousel.stopListening();
    complexCarousel.undelegateEvents();
    complexCarousel.listening = false;
  }

  //if we've gotten to a page with a list of collection mosaics, init infinite scroll
  //TODO: change reference to localhost!
  if($('#js-mosaicContainer').length > 0) {
    $('#js-mosaicContainer').infinitescroll({
      navSelector: '#js-collectionPagination',
      nextSelector: '#js-collectionPagination a.js-next',
      itemSelector: '#js-mosaicContainer div.js-collectionMosaic',
      debug: false,
      loading: {
        finishedMsg: 'All collections showing.',
        img: 'http://localhost:9000/images/orange-spinner.gif',
        msgText: '',
        selector: '#js-loading'
      }
    });
  }
};

$(document).ready(function() {
  $('html').removeClass('no-jquery');
  if ($(window).width() > 900) { DESKTOP = true; }
  else { DESKTOP = false; }

  $.pjax.defaults.timeout = 5000;
  $(document).pjax('a[data-pjax=js-pageContent]', '#js-pageContent');

  qm = new QueryManager();
  globalSearchForm = new GlobalSearchForm({model: qm});
  setupObjects();
  
  $('#js-global-header-logo').on('click', function() {
    if (!_.isEmpty(qm.attributes) || !_.isEmpty(sessionStorage)) {
      qm.clear();
    }
  });

  $(document).on('pjax:beforeSend', '#js-itemContainer', function(e, xhr, options) {
    if (options.container === '#js-itemContainer') {
      xhr.setRequestHeader('X-From-Item-Page', 'true');
    }
  });

  $(document).on('pjax:beforeReplace', '#js-pageContent', function() {
    if($('#js-mosaicContainer').length > 0) {
      $('#js-mosaicContainer').infinitescroll('destroy');
    }
  });

  $(document).on('pjax:end', '#js-itemContainer', function() {
    var lastLinkItem = $('.carousel__link--selected');
    if (lastLinkItem.data('item_id') !== qm.get('itemId')) {
      lastLinkItem.find('.carousel__image--selected').toggleClass('carousel__image');
      lastLinkItem.find('.carousel__image--selected').toggleClass('carousel__image--selected');
      lastLinkItem.toggleClass('carousel__link');
      lastLinkItem.toggleClass('carousel__link--selected');
      lastLinkItem.parent().toggleClass('carousel__item');
      lastLinkItem.parent().toggleClass('carousel__item--selected');

      var linkItem = $('.js-item-link[data-item_id="' + qm.get('itemId') + '"]');
      linkItem.find('.carousel__image').toggleClass('carousel__image--selected');
      linkItem.find('.carousel__image').toggleClass('carousel__image');
      linkItem.toggleClass('carousel__link--selected');
      linkItem.toggleClass('carousel__link');
      linkItem.parent().toggleClass('carousel__item--selected');
      linkItem.parent().toggleClass('carousel__item');
    }
  });

  $(document).on('pjax:end', '#js-pageContent', function() {
    //if we've gotten to a page without search context, clear the query manager
    if($('#js-facet').length <= 0 && $('#js-objectViewport').length <= 0) {
      qm.clear({silent: true});        
    }
    setupObjects();
  });
});

if(!('backgroundBlendMode' in document.body.style)) {
    // No support for background-blend-mode
  var html = document.getElementsByTagName('html')[0];
  html.className = html.className + ' no-background-blend-mode';
}