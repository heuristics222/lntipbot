#LNTipBot
Send and receive tips via the ⚡⚡**[LIGHTNING NETWORK](https://lightning.network/)**⚡⚡

###Status
* I sometimes do node maintenance on weekend nights, PST, during which time deposits and withdraws will be delayed.

###Purpose
This bot is intended to both promote awareness of the Lightning Network and high quality discussion about bitcoin and LN.  If you appreciate someone's post/comment that you feel positively contributes to the community, consider tipping!

###How it works
Make a reply to a post or comment on one of the active subreddits and the bot will parse your comment and either

* transfer satoshis from your balance to the parent's balance, or
* reply with an invoice you can pay which will credit the parent.

Some currently active subreddits are:

* /r/Bitcoin
* /r/BitcoinCA
* /r/lightningnetwork
* /r/bisq
* /r/de_krypto
* /r/TheLightningNetwork
* /r/raspibolt

###Commands
For all commands, omit the <>
####Public comments
* **!LNTIP <satoshis>** - Tips the parent post or comment the given amount in satoshis

####Private [messages](https://www.reddit.com/message/compose/?to=lntipbot) in the message body
* **!balance** - The bot will reply with your current balance in satoshis
* **!deposit <satoshis>** - The bot will reply with a LN invoice you can pay to credit your balance.  *Make sure to request a new invoice for each deposit!*
* **!withdraw <invoice>** - If your invoice has an amount, the bot will attempt to pay that amount if you have enough balance.  If your invoice does not have an amount, the bot will attempt to pay your entire balance.

###FAQ
####What does a lightning invoice look like?
* Here's an example:

>lnbc1u1pw56zdypp5xj2cudlluuya6pvrqqmyg7n7plp5ha8298e6jkkkevzglkkph8cqdqqcqzpgqk0c8y3654qnulpt3ugn80echqaqt87h9hfv2fsxlt82s8uf0agxd9lfh9anp5cl2mwvp45jtry8gwt4j0d5x03y4v9vkex3mu3dqqsq3269du

####I withdrew my balance but didn't receive any payment.

* If the payment fails, the balance will return.
* If the balance wasn't returned, the bot is still trying to make the payment.  The LN node may be down or have some other issue.  Give it some time.
* Make sure your LN node has a channel with enough remote balance.
* Try withdrawing a smaller amount, there might not be a path that can handle the requested amount.

####I got a tip but don't have a LN node to withdraw to, what can I do?

* You can use the bot like a wallet to deposit into other LN services.  Any service that creates invoices can be used with the withdraw bot command.  For example, you can read some articles on [yalls](https://yalls.org) by copying the invoices from yalls into a withdraw command.
* You might want to check out a custodial wallet (there are some listed here: https://lightningnetworkstores.com/wallets ) but **do make sure to do your research before trying out any of these**!
* Tip it forward!

####Can I withdraw my funds on-chain?

* Not at this time - if you'd like this service please let me know.

####The bot didn't respond to me.

* The bot polls for new messages and comments about every 15 seconds.
* Make sure to format your command correctly.  See above.
* It may be throttled on the subreddit, give it some upvotes to reduce the chance of this happening again.
* The tip limits are currently between 500 and 250,000 satoshis.

####Can I get this bot active in my subreddit?

* I'll gladly activate it with a request from a moderator of the sub, it only takes a minute. [Send me a message](https://www.reddit.com/message/compose/?to=drmoore718).

####What happens to the network fees?

* When you make a deposit or LN transaction from your node, your node will cover the fee.  When you make a withdrawal, my node will cover the fee.  Balances are not impacted by the network fees.  They're usually only 1 satoshi anyway.

####Want to connect directly to my nodes?
    021ccdea8971231aa618468f3730057a5b31c292b0b0e35c9118e465c94b23bae9@34.213.39.120:9735
    021ccdea8971231aa618468f3730057a5b31c292b0b0e35c9118e465c94b23bae9@[2600:1f14:741:4a00:fedc:ba98:7654:3210]:9735
    0219c2f8818bd2124dcc41827b726fd486c13cdfb6edf4e1458194663fb07891c7@64.187.175.226:9735

####I'm having trouble copying the invoice in the reddit app

* Included in the bot's response is a link to an invoice QR code and URI that will allow you to scan or copy.  Unfortunately, the URI can't be put directly in the comment because reddit markup won't allow it.

####I have some other issue.

* [Send me a message](https://www.reddit.com/message/compose/?to=drmoore718)

###Future
I am looking into using [HODL invoices](https://lightningwiki.net/index.php/HODL_Invoice) to remove the custodial account-like way the bot currently works.  How would it work?

* A new command, say `!hodltip`, is now used for tipping.
* When a tip is made, the bot will acknowledge it with a reply and also DM the tipper with a HODL invoice to pay.
* The tipper pays the invoice within the invoice timeout period (probably something like 2 days)
* Once the invoice is paid (but not settled yet by the bot), the tip recipient will be notified to supply an invoice for the same amount.
* If the tip recipient supplies an invoice within the HODL timeout, the bot will attempt to pay the invoice.  If successful, it will settle the tipper's invoice and the transaction is complete.
* If the tip recipient does not supply an invoice within the timeout, the tipper's invoice will expire and funds are returned to the tipper.

Advantages

* Less trust in the bot since balances are no longer needed.
* No risk of loss due to lost access to reddit account.
* Refunds now possible if the tip recipient is not interested in redeeming.

Disadvantages

* Tippers/tip recipients need to pay/create an invoice for every tip they make/receive.


The original way of tipping as well as withdrawals would still be supported indefinitely, but I will likely disable deposits going forward once this new method is up and running.


###Like the bot?
Tip the bot!
