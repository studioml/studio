import unittest
import sys

from studio.model import FirebaseProvider

class FirebaseProviderTest(unittest.TestCase):

    def getFirebaseProvider(self):
        dbUrl = "https://studio-ed756.firebaseio.com/"
        dbSecret = "3NE3ONN9CJgjqhC5Ijlr9DTNXmmyladvKhD2AbLk"
        return FirebaseProvider(dbUrl, dbSecret)

    def testGet(self):
        fb = self.getFirebaseProvider()
        response = fb.db.get("test/hello", None)
        self.assertTrue(response, "world")

        response = fb.db.get("test/", "hello")
        self.assertTrue(response, "world")



if __name__ == "__main__":
    unittest.main()

