PS C:\Users\Abdullah\Projects\django\Sync>  tree "C:\Users\Abdullah\Projects\django\Sync" /F /A     
>> >> Folder PATH listing for volume OS
>> >> Volume serial number is A234-77E2
>> 
Folder PATH listing for volume OS
Volume serial number is A234-77E2
C:\USERS\ABDULLAH\PROJECTS\DJANGO\SYNC
|   .env
|   .env.example
|   .gitignore
|   api-reference.md
|   docker-compose.yml
|   Dockerfile
|   pytest.ini
|   README.md
|   refactor_views.py
|   requirements.txt
|
+---.pytest_cache
|   |   .gitignore
|   |   CACHEDIR.TAG
|   |   README.md
|   |
|   \---v
|       \---cache
|               lastfailed
|               nodeids
|               stepwise
|
+---apps
|   |   __init__.py
|   |
|   +---accounts
|   |   |   admin.py
|   |   |   apps.py
|   |   |   audit.py
|   |   |   authentication.py
|   |   |   cookies.py
|   |   |   managers.py
|   |   |   middleware.py
|   |   |   models.py
|   |   |   permissions.py
|   |   |   schema.py
|   |   |   serializers.py
|   |   |   signing.py
|   |   |   tests.py
|   |   |   throttles.py
|   |   |   tokens.py
|   |   |   urls.py
|   |   |   utils.py
|   |   |   validators.py
|   |   |   views.py
|   |   |   __init__.py
|   |   |
|   |   +---migrations
|   |   |   |   0001_initial.py
|   |   |   |   0002_alter_employee_options_alter_user_managers_and_more.py
|   |   |   |   0003_alter_employee_created_at_alter_employee_updated_at.py
|   |   |   |   0004_alter_role_name.py
|   |   |   |   0005_employee_must_change_password_and_more.py
|   |   |   |   0006_profile.py
|   |   |   |   __init__.py
|   |   |   |
|   |   |   \---__pycache__
|   |   |           0001_initial.cpython-312.pyc
|   |   |           0002_alter_employee_options_alter_user_managers_and_more.cpython-312.pyc        
|   |   |           0003_alter_employee_created_at_alter_employee_updated_at.cpython-312.pyc        
|   |   |           0004_alter_role_name.cpython-312.pyc
|   |   |           0005_employee_must_change_password_and_more.cpython-312.pyc
|   |   |           0006_profile.cpython-312.pyc
|   |   |           __init__.cpython-312.pyc
|   |   |
|   |   +---tests
|   |   |   |   conftest.py
|   |   |   |   test_auth_flow.py
|   |   |   |   test_middleware.py
|   |   |   |   __init__.py
|   |   |   |
|   |   |   \---__pycache__
|   |   |           conftest.cpython-312-pytest-7.4.4.pyc
|   |   |           test_auth_flow.cpython-312-pytest-7.4.4.pyc
|   |   |           test_middleware.cpython-312-pytest-7.4.4.pyc
|   |   |           __init__.cpython-312.pyc
|   |   |
|   |   \---__pycache__
|   |           admin.cpython-312.pyc
|   |           apps.cpython-312.pyc
|   |           audit.cpython-312.pyc
|   |           authentication.cpython-312.pyc
|   |           cookies.cpython-312.pyc
|   |           middleware.cpython-312.pyc
|   |           models.cpython-312.pyc
|   |           permissions.cpython-312.pyc
|   |           schema.cpython-312.pyc
|   |           serializers.cpython-312.pyc
|   |           throttles.cpython-312.pyc
|   |           tokens.cpython-312.pyc
|   |           urls.cpython-312.pyc
|   |           utils.cpython-312.pyc
|   |           views.cpython-312.pyc
|   |           __init__.cpython-312.pyc
|   |
|   +---notifications
|   |   |   admin.py
|   |   |   apps.py
|   |   |   consumers.py
|   |   |   fcm_utils.py
|   |   |   middleware.py
|   |   |   models.py
|   |   |   routing.py
|   |   |   serializers.py
|   |   |   signals.py
|   |   |   tests.py
|   |   |   urls.py
|   |   |   utils.py
|   |   |   views.py
|   |   |   __init__.py
|   |   |
|   |   \---migrations
|   |           0001_initial.py
|   |           __init__.py
|   |
|   +---tasks
|   |   |   admin.py
|   |   |   apps.py
|   |   |   models.py
|   |   |   selectors.py
|   |   |   serializers.py
|   |   |   signals.py
|   |   |   state_machine.py
|   |   |   tests.py
|   |   |   urls.py
|   |   |   views.py
|   |   |   __init__.py
|   |   |
|   |   +---migrations
|   |   |   |   0001_initial.py
|   |   |   |   0002_remove_maintask_attachments_and_more.py
|   |   |   |   __init__.py
|   |   |   |
|   |   |   \---__pycache__
|   |   |           0001_initial.cpython-312.pyc
|   |   |           __init__.cpython-312.pyc
|   |   |
|   |   \---__pycache__
|   |           admin.cpython-312.pyc
|   |           apps.cpython-312.pyc
|   |           models.cpython-312.pyc
|   |           __init__.cpython-312.pyc
|   |
|   \---__pycache__
|           __init__.cpython-312.pyc
|
+---media
+---staticfiles
\---sync
    |   firebase-service-account.json
    |   manage.py
    |
    +---core
    |   |   asgi.py
    |   |   settings.py
    |   |   settings_test.py
    |   |   urls.py
    |   |   wsgi.py
    |   |   __init__.py
    |   |
    |   \---__pycache__
    |           settings.cpython-312.pyc
    |           settings_test.cpython-312-pytest-7.4.4.pyc
    |           urls.cpython-312.pyc
    |           __init__.cpython-312.pyc
    |
    +---media
    \---staticfiles
        +---admin
        |   +---css
        |   |   |   autocomplete.css
        |   |   |   base.css
        |   |   |   changelists.css
        |   |   |   dark_mode.css
        |   |   |   dashboard.css
        |   |   |   forms.css
        |   |   |   login.css
        |   |   |   nav_sidebar.css
        |   |   |   responsive.css
        |   |   |   responsive_rtl.css
        |   |   |   rtl.css
        |   |   |   unusable_password_field.css
        |   |   |   widgets.css
        |   |   |
        |   |   \---vendor
        |   |       \---select2
        |   |               LICENSE-SELECT2.md
        |   |               select2.css
        |   |               select2.min.css
        |   |
        |   +---img
        |   |   |   calendar-icons.svg
        |   |   |   icon-addlink.svg
        |   |   |   icon-alert.svg
        |   |   |   icon-calendar.svg
        |   |   |   icon-changelink.svg
        |   |   |   icon-clock.svg
        |   |   |   icon-deletelink.svg
        |   |   |   icon-hidelink.svg
        |   |   |   icon-no.svg
        |   |   |   icon-unknown-alt.svg
        |   |   |   icon-unknown.svg
        |   |   |   icon-viewlink.svg
        |   |   |   icon-yes.svg
        |   |   |   inline-delete.svg
        |   |   |   LICENSE
        |   |   |   README.txt
        |   |   |   search.svg
        |   |   |   selector-icons.svg
        |   |   |   sorting-icons.svg
        |   |   |   tooltag-add.svg
        |   |   |   tooltag-arrowright.svg
        |   |   |
        |   |   \---gis
        |   |           move_vertex_off.svg
        |   |           move_vertex_on.svg
        |   |
        |   \---js
        |       |   actions.js
        |       |   autocomplete.js
        |       |   calendar.js
        |       |   cancel.js
        |       |   change_form.js
        |       |   core.js
        |       |   filters.js
        |       |   inlines.js
        |       |   jquery.init.js
        |       |   nav_sidebar.js
        |       |   popup_response.js
        |       |   prepopulate.js
        |       |   prepopulate_init.js
        |       |   SelectBox.js
        |       |   SelectFilter2.js
        |       |   theme.js
        |       |   unusable_password_field.js
        |       |   urlify.js
        |       |
        |       +---admin
        |       |       DateTimeShortcuts.js
        |       |       RelatedObjectLookups.js
        |       |
        |       \---vendor
        |           +---jquery
        |           |       jquery.js
        |           |       jquery.min.js
        |           |       LICENSE.txt
        |           |
        |           +---select2
        |           |   |   LICENSE.md
        |           |   |   select2.full.js
        |           |   |   select2.full.min.js
        |           |   |
        |           |   \---i18n
        |           |           af.js
        |           |           ar.js
        |           |           az.js
        |           |           bg.js
        |           |           bn.js
        |           |           bs.js
        |           |           ca.js
        |           |           cs.js
        |           |           da.js
        |           |           de.js
        |           |           dsb.js
        |           |           el.js
        |           |           en.js
        |           |           es.js
        |           |           et.js
        |           |           eu.js
        |           |           fa.js
        |           |           fi.js
        |           |           fr.js
        |           |           gl.js
        |           |           he.js
        |           |           hi.js
        |           |           hr.js
        |           |           hsb.js
        |           |           hu.js
        |           |           hy.js
        |           |           id.js
        |           |           is.js
        |           |           it.js
        |           |           ja.js
        |           |           ka.js
        |           |           km.js
        |           |           ko.js
        |           |           lt.js
        |           |           lv.js
        |           |           mk.js
        |           |           ms.js
        |           |           nb.js
        |           |           ne.js
        |           |           nl.js
        |           |           pl.js
        |           |           ps.js
        |           |           pt-BR.js
        |           |           pt.js
        |           |           ro.js
        |           |           ru.js
        |           |           sk.js
        |           |           sl.js
        |           |           sq.js
        |           |           sr-Cyrl.js
        |           |           sr.js
        |           |           sv.js
        |           |           th.js
        |           |           tk.js
        |           |           tr.js
        |           |           uk.js
        |           |           vi.js
        |           |           zh-CN.js
        |           |           zh-TW.js
        |           |
        |           \---xregexp
        |                   LICENSE.txt
        |                   xregexp.js
        |                   xregexp.min.js
        |
        \---rest_framework
            +---css
            |       bootstrap-theme.min.css
            |       bootstrap-theme.min.css.map
            |       bootstrap-tweaks.css
            |       bootstrap.min.css
            |       bootstrap.min.css.map
            |       default.css
            |       font-awesome-4.0.3.css
            |       prettify.css
            |
            +---docs
            |   +---css
            |   |       base.css
            |   |       highlight.css
            |   |       jquery.json-view.min.css
            |   |
            |   +---img
            |   |       favicon.ico
            |   |       grid.png
            |   |
            |   \---js
            |           api.js
            |           highlight.pack.js
            |           jquery.json-view.min.js
            |
            +---fonts
            |       fontawesome-webfont.eot
            |       fontawesome-webfont.svg
            |       fontawesome-webfont.ttf
            |       fontawesome-webfont.woff
            |       glyphicons-halflings-regular.eot
            |       glyphicons-halflings-regular.svg
            |       glyphicons-halflings-regular.ttf
            |       glyphicons-halflings-regular.woff
            |       glyphicons-halflings-regular.woff2
            |
            +---img
            |       glyphicons-halflings-white.png
            |       glyphicons-halflings.png
            |       grid.png
            |
            \---js
                    ajax-form.js
                    bootstrap.min.js
                    coreapi-0.1.1.js
                    csrf.js
                    default.js
                    jquery-3.7.1.min.js
                    load-ajax-form.js
                    prettify-min.js