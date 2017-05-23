import unittest
import sys
import uuid

from studio.model import FirebaseProvider

class FirebaseProviderTest(unittest.TestCase):

    def getFirebaseProvider(self):
        dbUrl = "https://studio-ed756.firebaseio.com/"
        dbSecret = "3NE3ONN9CJgjqhC5Ijlr9DTNXmmyladvKhD2AbLk"
        return FirebaseProvider(dbUrl, dbSecret)

    def testGetSet(self):
        fb = self.getFirebaseProvider()
        response = fb["test/hello"]
        self.assertTrue(response, "world")
        
        randomStr = str(uuid.uuid4())
        keyPath = 'test/randomKey'
        fb[keyPath] = randomStr

        self.assertTrue(fb[keyPath] == randomStr)
        fb.delete(keyPath)



if __name__ == "__main__":
    unittest.main()

