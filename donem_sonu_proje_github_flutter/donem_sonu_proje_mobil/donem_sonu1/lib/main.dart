import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_mjpeg/flutter_mjpeg.dart';
import 'dart:convert';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sandalye Durumu',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: SandalyeDurumu(),
    );
  }
}

class SandalyeDurumu extends StatefulWidget {
  @override
  _SandalyeDurumuState createState() => _SandalyeDurumuState();
}

class _SandalyeDurumuState extends State<SandalyeDurumu> {
  Map<String, dynamic> _data = {};

  @override
  void initState() {
    super.initState();
    fetchData();
  }

  Future<void> fetchData() async {
    try {
      final response =
          await http.get(Uri.parse('http://172.18.29.145:5000/veri'));

      if (response.statusCode == 200) {
        setState(() {
          _data = json.decode(response.body);
        });
      } else {
        throw Exception('Veri alınamadı!');
      }
    } catch (e) {
      print('Hata: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Sandalye Durumu'),
      ),
      body: RefreshIndicator(
        onRefresh: fetchData,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: _data.isEmpty
                ? Center(child: CircularProgressIndicator())
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Kamera Akışı
                      Card(
                        elevation: 5,
                        margin: EdgeInsets.only(bottom: 16),
                        child: AspectRatio(
                          aspectRatio: 16 / 9,
                          child: Mjpeg(
                            stream:
                                'http://172.18.28.154:4747/video', // Kendi MJPEG adresin
                            isLive: true,
                          ),
                        ),
                      ),
                      // Toplam Sandalye
                      _buildCard(
                        icon: Icons.chair,
                        iconColor: Colors.blue,
                        title: 'Toplam Sandalye',
                        value: _data['toplam'],
                      ),
                      // Dolu Sandalye
                      _buildCard(
                        icon: Icons.event_seat,
                        iconColor: Colors.green,
                        title: 'Dolu Sandalye',
                        value: _data['dolu'],
                      ),
                      // Boş Sandalye
                      _buildCard(
                        icon: Icons.airline_seat_recline_normal,
                        iconColor: Colors.red,
                        title: 'Boş Sandalye',
                        value: _data['bos'],
                      ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }

  Widget _buildCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required dynamic value,
  }) {
    return Card(
      elevation: 5,
      margin: EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: Icon(icon, color: iconColor),
        title: Text(
          title,
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          '$value',
          style: TextStyle(fontSize: 18, color: Colors.black87),
        ),
      ),
    );
  }
}
