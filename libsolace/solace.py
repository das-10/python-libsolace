
import libsolace.settingsloader as settings
import logging
from libsolace import xml2dict
import pprint

try:
    from collections import OrderedDict
except:
    from ordereddict import OrderedDict

try:
    import simplejson
except:
    from json import simplejson

from libsolace.util import httpRequest, generateRequestHeaders, generateBasicAuthHeader


class SolaceAPI:
    """ Used by SolaceHelper, Use directly only if you know what you're doing. See SolaceHelper rather. """
    def __init__(self, environment, testmode=False, **kwargs):
        try:
            logging.debug("Solace Client initializing")
            self.config = settings.SOLACE_CONF[environment]
            logging.debug("Loaded Config: %s" % self.config)
            self.testmode = testmode
            if 'VERIFY_SSL' not in self.config:
                self.config['VERIFY_SSL'] = True
            if testmode:
                self.config['USER'] = settings.READ_ONLY_USER
                self.config['PASS'] = settings.READ_ONLY_PASS
                logging.info('READONLY mode')
            logging.debug("Final Config: %s" % self.config)
        except Exception, e:
            logging.warn("Solace Error %s" %e)
            raise BaseException("Configuration Error")

    def __restcall(self, request, **kwargs):
        logging.info("%s user requesting: %s" % (self.config['USER'], request))
        self.kwargs = kwargs
        try:
            data = OrderedDict()
            for host in self.config['MGMT']:

                #url = '%s://%s/SEMP' % (self.config['PROTOCOL'].lower(), host)
                url = host
                request_headers = generateRequestHeaders(
                    default_headers = {
                      'Content-type': 'text/xml',
                      'Accept': 'text/xml'
                    },
                    auth_headers = generateBasicAuthHeader(self.config['USER'], self.config['PASS'])
                )
                (response, response_headers, code) = httpRequest(url, method='POST', headers=request_headers, fields=request, timeout=5000, verifySsl = self.config['VERIFY_SSL'])
                data[host]=response
            logging.debug(data)

            for k in data:
                thisreply = xml2dict.parse(data[k])
                if thisreply['rpc-reply'].has_key('execute-result'):
                    if thisreply['rpc-reply']['execute-result']['@code'] != 'ok':
                        logging.warn("Device: %s: %s %s" % (k, thisreply['rpc-reply']['execute-result']['@code'],
                                                                 "Request that failed: %s" % request))
                        logging.warn("Device: %s: %s: %s" % (k, thisreply['rpc-reply']['execute-result']['@code'],
                                                                    "Reply from appliance: %s" % thisreply['rpc-reply']['execute-result']['@reason']))
                    else:
                        logging.info("Device: %s: %s" % (k, thisreply['rpc-reply']['execute-result']['@code']))
                    logging.debug("Device: %s: %s" % (k, thisreply))
                else:
                    logging.debug("no execute-result in response. Device: %s" % k)
            logging.debug("Returning Data from rest_call")
            return data

        except Exception, e:
            logging.warn("Solace Error %s" % e )
            raise

    def get_redundancy(self):
        """ Return redundancy information """
        try:
            request = '<rpc semp-version="soltr/6_0"><show><redundancy></redundancy></show></rpc>'
            return self.rpc(request)
        except:
            raise


    def get_memory(self):
        """ Returns the Memory Usage """
        try:
            request ='<rpc semp-version="soltr/6_0"><show><memory></memory></show></rpc>'
            return self.rpc(request)
        except:
            raise

    def get_queue(self, queue, vpn, detail=False, **kwargs):
        """ Return Queue details """
        try:
            extras = []
            if detail:
                extras.append('<detail/>')
            request = '<rpc semp-version="soltr/6_0"><show><queue><name>%s</name>' \
                      '<vpn-name>%s</vpn-name>%s</queue></show></rpc>' % (queue, vpn, "".join(extras))
            return self.rpc(request)
        except:
            raise

    def list_queues(self, vpn, queue_filter='*'):
        """ List all queues in a VPN """
        try:
            request = '<rpc semp-version="soltr/6_0"><show><queue><name>%s</name>' \
                      '<vpn-name>%s</vpn-name></queue></show></rpc>' % (queue_filter, vpn)
            response = self.rpc(request)
            logging.debug(response)
            queues = []
            for k in response:
                logging.debug("Response: %s" % k)
                try:
                    myq = [ queue['name'] for queue in k['rpc-reply']['rpc']['show']['queue']['queues']['queue'] ]
                    for q in myq:
                        queues.append(q)
                except TypeError, e:
                    logging.warn("Atttibute Error %s" % e)
                    try:
                        queues.append(k['rpc-reply']['rpc']['show']['queue']['queues']['queue']['name'])
                    except:
                        logging.warn("Error %s" % e)
                        pass
                logging.debug(queues)
            return queues
        except Exception, e:
            logging.warn("Solace Exception, %s" % e)
            raise

    def get_client_username_queues(self, client_username, vpn):
        """
        Returns a list of queues owned by user
        """
        result = []
        response = self.get_queue('*', vpn, detail=True)
        #queue_list = lambda x,y: [ yy['name'] for yy in y if yy['info']['owner'] == x ]
        queue_list = {
            list: lambda x: [ y['name'] for y in x if y['info']['owner'] == client_username ],
            dict: lambda x: [ y['name'] for y in [x] if y['info']['owner'] == client_username ]
            }
        try:
            for h in response:
                if h['rpc-reply']['rpc']['show']['queue'] != None and h['rpc-reply']['rpc']['show']['queue']['queues'] != None:
                    queues = h['rpc-reply']['rpc']['show']['queue']['queues']['queue']
                    result.extend(queue_list[type(queues)](queues))
        except KeyError, e:
            raise Exception("While getting list of queues from get_queue() the response did not contain the expected data. VPN: %s. Exception message: %s" % (vpn,str(e)))
        else:
            return result

    def is_client_username_inuse(self, client_username, vpn):
        """
        Returns boolean if client username has client connections
        """
        result = []
        response = self.get_client('*', vpn, detail=True)
        in_use = lambda x,y: [ True for yy in y if yy['client-username'] == x ]
        try:
            for h in response:
                if h['rpc-reply']['rpc']['show']['client'].has_key('primary-virtual-router'):
                    result = in_use(client_username,h['rpc-reply']['rpc']['show']['client']['primary-virtual-router']['client'])
        except KeyError, e:
            raise Exception("While getting list of connection from get_client() the response did not contain the expected data. VPN: %s. Exception message: %s" % (vpn,str(e)))
        else:
            return result.count(True) > 0

    def does_client_username_exist(self, client_username, vpn):
        """
        Returns boolean if client username exists inside vpn
        """
        response = self.get_client_username(client_username, vpn)
        try:
            result = [ x for x in response if x['rpc-reply']['rpc']['show']['client-username']['client-usernames'] != None and x['rpc-reply']['rpc']['show']['client-username']['client-usernames']['client-username']['client-username'] == client_username ]
        except TypeError, e:
            raise Exception("Client username not consistent across all nodes. Message: %s" % str(e))
        else:
            if len(result) > 0 and len(result) < len(response):
                msg = "Client username not consistent across all nodes, SEMP: %s" % str(result)
                logging.error(msg)
                raise Exception(msg)
            elif len(result) == len(response):
                return True
            else:
                return False

    def is_client_username_enabled(self, client_username, vpn):
        """
        Returns boolean if client username inside vpn is enabled
        """
        response = self.get_client_username(client_username, vpn)
        evaluate = lambda x: x['client-username'] == client_username and x['enabled'] == 'true'
        result = [ evaluate(x['rpc-reply']['rpc']['show']['client-username']['client-usernames']['client-username']) for x in response
                      if x['rpc-reply']['rpc']['show']['client-username']['client-usernames'] != None ]
        if len(result) == 0:
            raise Exception("Client username %s not found" % client_username)
        elif len(result) < len(response):
            raise Exception("Client username %s not consistent. Does not exist on all nodes" % client_username)
        if (not result[0]) in result:
            raise Exception("Client username %s not consistent. Enabled and disabled on some nodes" % client_username)
        else:
            return result[0]

    def get_client_username(self, clientusername, vpn, detail=False, **kwargs):
        """
        Get client username details
        """
        extras = []
        if detail:
            extras.append('<detail/>')
        request = '<rpc semp-version="soltr/6_0"><show><client-username>' \
                  '<name>%s</name><vpn-name>%s</vpn-name>%s</client-username></show></rpc>' % ( clientusername, vpn, "".join(extras))
        return self.rpc(request)

    def get_client(self, client, vpn, detail=False, **kwargs):
        """ Get Client details """
        extras = []
        if detail:
            extras.append('<detail/>')
        try:
            request = '<rpc semp-version="soltr/6_0"><show><client>' \
                      '<name>%s</name><vpn-name>%s</vpn-name>%s</client></show></rpc>' % ( client, vpn, "".join(extras))
            return self.rpc(request)
        except:
            raise

    def get_vpn(self, vpn, stats=False):
        """ Get VPN details """
        extras = []
        if stats:
            extras.append('<stats/>')
        try:
            request = '<rpc semp-version="soltr/5_5"><show><message-vpn>' \
                      '<vpn-name>%s</vpn-name>%s</message-vpn></show></rpc>' % ( vpn, "".join(extras))
            return self.rpc(request)
        except:
            raise

    def list_vpns(self, vpn):
        try:
            request = '<rpc semp-version="soltr/5_5"><show><message-vpn><vpn-name>%s</vpn-name>' \
                      '<replication/></message-vpn></show></rpc>' % vpn
            response = self.rpc(request)
            try:
                return [vpn['vpn-name'] for vpn in response[0]['rpc-reply']['rpc']['show']['message-vpn']['replication']['message-vpns']['message-vpn']]
            except:
                return [response[0]['rpc-reply']['rpc']['show']['message-vpn']['replication']['message-vpns']['message-vpn']['vpn-name']]
        except:
            raise

    def rpc(self, xml, allowfail=False,  **kwargs):
        ''' Ships XML string direct to the Solace RPC '''
        try:
            data = []
            responses = self.__restcall(xml)
            for k in responses:
                response = xml2dict.parse(responses[k])
                logging.debug(response)
                response['HOST'] = k
                if not allowfail:
                    if response['rpc-reply'].has_key('parse-error'):
                        raise Exception(str(response))
                    elif response['rpc-reply'].has_key('permission-error'):
                        if self.testmode:
                            logging.debug('tollerable permission error in test mode')
                        else:
                            logging.critical("Sholly Hit! Request was: %s" % xml)
                            raise Exception(str(response))
                    else:
                        data.append(response)
                else:
                    data.append(response)
            return data
        except:
            raise
