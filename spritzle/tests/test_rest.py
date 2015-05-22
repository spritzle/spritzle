import spritzle.main
from spritzle.rest import delete, get, post, put

import webtest
app = webtest.TestApp(spritzle.main.bottle.app())

@delete('/test_delete')
def delete():
    pass

@get('/test_get')
def get():
    pass

@post('/test_post')
def post(arg):
    pass

@put('/test_put')
def put(arg):
    pass

def test_delete():
    response = app.delete('/test_delete')
    assert response.status == '200 OK'
    assert response.content_type == 'application/json'

def test_get():
    response = app.get('/test_get')
    assert response.status == '200 OK'
    assert response.content_type == 'application/json'

def test_post():    
    response = app.post('/test_post')
    assert response.status == '200 OK'
    assert response.content_type == 'application/json'

def test_put():
    response = app.put('/test_put')
    assert response.status == '200 OK'
    assert response.content_type == 'application/json'
