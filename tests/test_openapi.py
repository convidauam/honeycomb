EXPECTED_OPERATION_IDS = {
    ('/api/v1/honeycombs', 'get'): 'listHoneycombs',
    ('/api/v1/honeycombs/{name}', 'get'): 'getHoneycomb',
    ('/api/v1/node/{node_id}', 'get'): 'getNode',
    ('/api/v1/me', 'get'): 'getMe',
    ('/api/v1/drones/{userid}', 'get'): 'getDrone',
    ('/api/v1/userid', 'get'): 'getUserId',
    ('/api/v1/sipping/{nodeid}', 'get'): 'getSippingData',
    ('/api/v1/sipping/{nodeid}', 'post'): 'saveSippingData',
    ('/api/v1/sipping/{nodeid}/badges', 'post'): 'awardBadge',
    ('/api/v1/achievements', 'get'): 'getAchievements',
    ('/api/v1/share', 'post'): 'shareAchievement',
}


def test_openapi_spec_available_without_auth(testapp):
    body = testapp.get('/openapi/openapi.json', status=200).json
    assert body['openapi'].startswith('3.')


def test_openapi_spec_lists_expected_operations(testapp):
    body = testapp.get('/openapi/openapi.json', status=200).json
    found = {
        (path, method): op['operationId']
        for path, methods in body['paths'].items()
        for method, op in methods.items()
    }
    assert found == EXPECTED_OPERATION_IDS
