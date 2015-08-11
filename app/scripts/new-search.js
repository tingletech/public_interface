/*global Backbone, _, DESKTOP */
/*exported GlobalSearchForm, FacetForm, CarouselContext */

'use strict';

var GlobalSearchForm = Backbone.View.extend({
  initialize: function() {
    //on submit, change the model, don't submit the form
    $('#js-searchForm, #js-footerSearch').on('submit', (function(model) {
      return function(e) { 
        model.set({q: $(this).find('input[name=q]').val()}); 
        e.preventDefault();
      };
    }(this.model)));
    
    // ##### Global Header ##### //

    // Toggle mobile menu with search box:
    // $('.js-global-header__bars-icon').click(function(){
    $(document).on('click', '.js-global-header__bars-icon', function() {
      $('.js-global-header__search').toggleClass('global-header__search global-header__search--selected');
      $('.js-global-header__mobile-links').toggleClass('.global-header__mobile-links global-header__mobile-links--selected');
    });

    // Toggle only search box:
    //  $('.js-global-header__search-icon').click(function(){
    $(document).on('click', '.js-global-header__search-icon', function() {
      $('.js-global-header__search').toggleClass('global-header__search global-header__search--selected');
    });

    //when the model changes, 
    this.listenTo(this.model, 'change:q', this.render);
  }, 
  
  render: function() {
    if(this.model.has('q')) {
      //get rid of all other search parameters
      var q = this.model.get('q');
      this.model.clear({silent: true});
      this.model.set({q: q}, {silent: true});
      //perform the search!
      $.pjax({
        url: $('#js-searchForm').attr('action'),
        container: '#js-pageContent',
        data: this.model.toJSON()
      });
    }
    
    _.each($('#js-searchForm, #js-footerSearch'), (function(model) {
      return function(form) {
        $('input[name=q][form=' + $(form).attr('id') + ']').val(model.get('q'));
      };
    }(this.model)));
  }
});

var FacetForm = Backbone.View.extend({
  initialize: function() {
    this.carouselRows = 12;
    
    $(document).on('submit', '#js-facet', (function(model) {
      return function(e) {
        model.set({start: 0, rq: $.map($('input[name=rq]'), function(el) { return $(el).val(); })});
        e.preventDefault();
      };
    }(this.model)));
    
    $(document).on('click', '.js-refine-filter-pill', (function(model) {
      return function() { 
        //update html
        var txtFilter = $(this).data('slug');
        $('input[form="js-facet"][name="rq"][value="' + txtFilter + '"]').val('');
        //update model
        // if (_.without(model.get('rq'), txtFilter).length === 0) {
        //   model.set({start: 0, rq: ''});
        // } else {
        model.set({start: 0, rq: _.without(model.get('rq'), txtFilter)});
        // }
      };
    }(this.model)));
    
    $(document).on('change', '.js-facet', (function(model) {
      return function() {
        var filterType = $(this).attr('name');
        var attributes = {start: 0};
        attributes[filterType] = $.map($('input[name=' + filterType + ']:checked'), function(el) { return $(el).val(); });
        model.set(attributes);
      };
    }(this.model)));
    
    $(document).on('click', '.js-filter-pill', (function(model) {
      return function() {
        var filter_slug = $(this).data('slug');
        if (typeof filter_slug !== 'string') {
          filter_slug = String(filter_slug);
        }
        $('#' + filter_slug).prop('checked', false);
        var filterType = $('#' + filter_slug).attr('name');
        var filter = $('#' + filter_slug).attr('value');
        var attributes = {start: 0};
        attributes[filterType] = _.without(model.get(filterType), filter);

        model.set(attributes);
      };
    }(this.model)));
    
    $(document).on('click', '#thumbnails', (function(model) {
      return function() { 
        $('#view_format').prop('value', 'thumbnails');
        model.set({view_format: 'thumbnails'}); 
      };
    }(this.model)));
    
    $(document).on('click', '#list', (function(model) {
      return function() { 
        $('#view_format').prop('value', 'list');
        model.set({view_format: 'list'}); 
      };
    }(this.model)));
    
    $(document).on('change', '#pag-dropdown__sort', (function(model) {
      return function() {
        model.set({start: 0, sort: $(this).val() });
      };
    }(this.model)));
    
    $(document).on('change', '#pag-dropdown__view', (function(model) {
      return function() {
        model.set({start: 0, rows: $(this).val() });
      };
    }(this.model)));
    
    $(document).on('click', '.js-prev, .js-next', (function(model) {
      return function() {
        var start = $(this).data('start');
        $('#start').val(start);
        model.set({ start: start });
      };
    }(this.model)));
    
    $(document).on('change', '.pag-dropdown__select--unstyled', (function(model){
      return function() {
        var start = $(this).children('option:selected').attr('value');
        $('#start').val(start);
        model.set({ start: start });
      };
    }(this.model)));
    
    $(document).on('click', 'a[data-start]', (function(model){
      return function() {
        var start = $(this).data('start');
        $('#start').val(start);
        model.set({ start: start });
      };
    }(this.model)));
    
    $(document).on('click', '.js-item-link', (function(that){
      return function(e) {
        if ($(this).data('item_number') !== undefined) {
          that.model.set({
            itemNumber: $(this).data('item_number'),
            carouselRows: that.carouselRows, 
            itemId: $(this).data('item_id')
          }, {silent: true});
          
          // add implicit context for campus, institution, and collection pages
          if($('#js-institution').length > 0) {
            if($('#js-institution').data('campus')) {
              that.model.set({campus: $('#js-institution').data('campus')}, {silent: true});
            } else {
              that.model.set({repository_data: $('#js-institution').data('institution')}, {silent: true});
            }
          } else if ($('#js-collection').length > 0) {
            that.model.set({collection_data: $('#js-collection').data('collection')}, {silent: true});
          }
          
          e.preventDefault();
          $.pjax({
            url: $(this).attr('href'),
            container: '#js-pageContent'
          });
        }
      };
    }(this)));

    $(document).on('click', '.js-a-check__link-deselect-all, .js-a-check__button-deselect-all', function(e){
      var filterElements = $(this).parents('.check').find('.js-facet');
      filterElements.prop('checked', false);
      filterElements.trigger('change');
      e.preventDefault();
    });
    
    $(document).on('click', '.js-a-check__link-select-all, .js-a-check__button-select-all', function(e){
      var filterElements = $(this).parents('.check').find('.js-facet');
      filterElements.prop('checked', true);
      filterElements.trigger('change');
      e.preventDefault();
    });

    $(document).on('click', '.js-clear-filters', function() {
      var filterElements = $('.js-facet');
      filterElements.prop('checked', false);
      filterElements.trigger('change');
    });

    // set up checkbox groups for small and medium screens
    $(document).on('click', '.js-a-check__header', function() {
      //close all expanded checkbox groups
      var allSelected = $('.check__popdown--selected');
      for (var i=0; i<allSelected.length; i++) {
        if ($(allSelected[i]).parent().find('input').attr('name') !== $(this).parent().find('input').attr('name')) {
          $(allSelected[i]).toggleClass('check__popdown check__popdown--selected');
          $(allSelected[i]).prev('.js-a-check__header').children('.js-a-check__header-arrow-icon').toggleClass('fa-angle-down fa-angle-up');
        }
      }
      //open this checkbox group
      $(this).next('.js-a-check__popdown').toggleClass('check__popdown check__popdown--selected');
      $(this).children('.js-a-check__header-arrow-icon').toggleClass('fa-angle-down fa-angle-up');
    });

    $(document).on('click', '.js-a-check__update', (function(that) {
      return function(e) {
        that.facetSearch();
        e.preventDefault();
      };
    }(this)));

    $(document).on('click', '.js-rc-page', (function(model) {
      return function() {
        var data_params = model.toJSON();
        data_params.rc_page = $(this).data('rc_page');
        //TODO: function(data, status, jqXHR)
        $.ajax({data: data_params, traditional: true, url: '/relatedCollections/', success: function(data) {
            $('#js-relatedCollections').html(data);
          }
        });
      };
    }(this.model)));

    this.listenTo(this.model, 'change', this.render);
  },
  
  toggleSelectDeselectAll: function() {
    var facetTypes = $('.check');
    for(var i=0; i<facetTypes.length; i++) {
      var allSelected = !($($(facetTypes[i]).find('.js-facet')).is(':not(:checked)'));
      if (allSelected === true) {
        // for large screens
        $(facetTypes[i]).find('.js-a-check__link-deselect-all').toggleClass('check__link-deselect-all--not-selected check__link-deselect-all--selected');
        $(facetTypes[i]).find('.js-a-check__link-select-all').toggleClass('check__link-select-all--selected check__link-select-all--not-selected');
        $(facetTypes[i]).find('.js-a-check__button-select-all').prop('disabled', true);
        $(facetTypes[i]).find('.js-a-check__update').prop('disabled', false);
      }
      var oneSelected = $(facetTypes[i]).find('.js-facet').is(':checked');
      if (oneSelected === true) {
        $(facetTypes[i]).find('.js-a-check__button-deselect-all').prop('disabled', false);
      }
    }
  },

  facetSearch: function() {
    $.pjax({
      url: $('#js-facet').attr('action'),
      container: '#js-pageContent',
      data: this.model.toJSON(),
      traditional: true
    });
  },

  render: function() {
    if(!_.isEmpty(this.model.changed) && !_.has(this.model.changed, 'q')) {
      if(DESKTOP) {
        this.facetSearch();
      }
      else if(_.has(this.model.changed, 'type_ss') ||
      _.has(this.model.changed, 'facet_decade') ||
      _.has(this.model.changed, 'repository_data') ||
      _.has(this.model.changed, 'collection_data')) {
        _.each(this.model.changed, function(value, key) {
          if (key === 'type_ss' || key === 'facet_decade' || key === 'repository_data' || key === 'collection_data') {
            $('.facet-' + key).parents('.check').find('.js-a-check__update').prop('disabled', false);
          }
        });
      }
    }
  }
});

var CarouselContext = Backbone.View.extend({
  initialize: function() {
    $('#js-linkBack').html('<a href="/search/">Search results for "' + this.model.get('q') + '"</a>');

    $(document).on('click', '#js-linkBack a', (function(that){
      return function(e) {
        that.model.unset('carouselStart', {silent: true});
        that.model.unset('carouselRows', {silent: true});
        that.model.unset('itemId', {silent: true});
        that.model.unset('itemNumber', {silent: true});
        e.preventDefault();
        $.pjax({
          url: $(this).attr('href'),
          container: '#js-pageContent',
          data: that.model.toJSON(),
          traditional: true
        });        
      };
    }(this)));
    
    this.model.set({carouselStart: this.model.get('itemNumber')}, {silent: true});

    var conf = {
      infinite: false,
      speed: 300,
      slidesToShow: 10,
      slidesToScroll: 6,
      variableWidth: true,
      lazyLoad: 'ondemand',
      responsive: [
        {
          breakpoint: 1200,
          settings: {
            infinite: true,
            // slidesToShow: 8,
            slidesToScroll: 8,
            variableWidth: true
          }
        },
        {
          breakpoint: 900,
          settings: {
            infinite: true,
            // slidesToShow: 6,
            slidesToScroll: 6,
            variableWidth: true
          }
        },
        {
          breakpoint: 650,
          settings: {
            infinite: true,
            // slidesToShow: 4,
            slidesToScroll: 4,
            variableWidth: true
          }
        }
      ]
    };    
    
    //TODO: function(data, status, jqXHR)
    $.ajax({
      url: '/carousel/',
      data: this.model.carouselContext(), 
      traditional: true, 
      success: function(data) {
        $('#js-carousel').html(data);
        $('.carousel').show();
        $('.carousel').slick(conf);
        $('.carousel__items-number').html($(data).data('numfound') + ' ' + $('.carousel__items-number').html());
      }
    });

    $('.carousel').on('beforeChange', (function(that) {
      return function(event, slick, currentSlide, nextSlide){
        var numFound = $('.js-carousel_item').data('numfound');
        var numLoaded = $('.carousel').slick('getSlick').slideCount;
        // var slidesPerPage = $('.carousel').slick('getSlick').options.slidesToScroll;

        if (numLoaded < numFound && nextSlide > currentSlide) {

          var data_params = that.model.carouselContext();
          data_params.start = parseInt(that.model.get('carouselStart')) + parseInt(that.model.get('carouselRows'));
          that.model.set({carouselStart: data_params.start}, {silent: true});

          // function(data, status, jqXHR)
          $.ajax({data: data_params, traditional: true, url: '/carousel/', success: function(data) {
              $('.carousel').slick('slickAdd', data);
          }});
        }

        // if (nextSlide+slidesPerPage > numFound){ var slideRange = (nextSlide+slidesPerPage) - numFound}
        // else { var slideRange = nextSlide+slidesPerPage }
        //
        // $('.carousel__items-number').text('Displaying ' + (parseInt(nextSlide)+1) + ' - ' + slideRange + ' of ' + numFound);

      };
    }(this)));
  }
});